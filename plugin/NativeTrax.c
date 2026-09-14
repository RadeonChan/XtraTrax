#include <windows.h>
#include <wincrypt.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* EA Layer 3 can exhaust its bit buffer while reading an extended magnitude.
   Fetch the following sign bit before testing it. Preserve the displaced CMP
   flags and MOV so the original decoder continues with the correct sign. */
__attribute__((naked)) static void layer3SignHook(void) {
 __asm__ volatile(
  "push %eax\n push %edx\n cmpl $0,0x34(%esi)\n jne 1f\n"
  "mov 0x24(%esi),%eax\n movzbl (%eax),%edx\n inc %eax\n"
  "mov %eax,0x24(%esi)\n shl $24,%edx\n mov %edx,0x30(%esi)\n"
  "movl $8,0x34(%esi)\n"
  "1: pop %edx\n pop %eax\n cmpl $0,0x30(%esi)\n mov 0xc(%ebp),%ecx\n ret");
}

typedef struct {const char *title,*artist,*album,*mode;} Metadata;
typedef struct {uint32_t index; BYTE mode,pad[3];} Setting;
#ifndef TRACK_COUNT
#define TRACK_COUNT 127
#endif
#if TRACK_COUNT < 28 || TRACK_COUNT > 127
#error Capacity test supports 28..127 rows; signed menu immediate must be audited beyond 127
#endif
static Metadata metadata[TRACK_COUNT];

typedef struct { char title[256],artist[256],album[256],key[65]; } PackTrack;
typedef struct { char magic[16]; unsigned count; BYTE archive[32]; PackTrack tracks[100]; } Package;
__declspec(dllexport) Package packageConfig={.magic="NATIVE_TRAX_V1"};
static unsigned trackCount=28;
__declspec(dllexport) unsigned forceWideBanners=0xFFFFFFFF;
__attribute__((used,noinline)) static int configurePackage(void) {
 if(forceWideBanners>1)return 0;
 if(memcmp(packageConfig.magic,"NATIVE_TRAX_V1",14) || packageConfig.count<1 || packageConfig.count>100)return 0;
 for(unsigned i=0;i<packageConfig.count;i++) {
  PackTrack *t=&packageConfig.tracks[i];
  if(!memchr(t->title,0,256)||!memchr(t->artist,0,256)||!memchr(t->album,0,256)||!memchr(t->key,0,65)||!t->title[0]||!t->key[0])return 0;
 }
 trackCount=27+packageConfig.count;return 1;
}

/* Test aliases share existing event79. No new audio/archive required. */
static volatile unsigned eventIds[TRACK_COUNT];
typedef struct { BYTE eligible[TRACK_COUNT], remaining[TRACK_COUNT]; int last; } Playlist;
static Playlist playlists[2];
static void *playlistOwner;
static int playlistReady;
/* A native scoped bag request is captured at its writer, not guessed by seed. */
static void *nativeRequestOwner;
static unsigned nativeRequestMask;
static int nativeRequestPending;
__attribute__((used,noinline)) static void captureNativeBag(void *player) {
 nativeRequestOwner=player;
 nativeRequestMask=*(unsigned*)((BYTE*)player+0x88);
 nativeRequestPending=1;
}
__attribute__((naked)) static void nativeBagHook(void) {
 __asm__ volatile("movl $1,0x88(%esi)\n pushfl\n pushal\n push %esi\n call _captureNativeBag\n add $4,%esp\n popal\n popfl\n push $0x47aede\n ret");
}
static int validExtra(int index) { return index>=27 && index<(int)trackCount; }

static Setting settings[TRACK_COUNT];
static char logpath[MAX_PATH];
__attribute__((used)) static void *menuTrampoline,*callbackTrampoline;
static int selected=-1;
static void logline(const char *s);
static int customPreview=-1;
static int tracing=0;
static char settingsPath[MAX_PATH];
static volatile int pendingAutomatic=-1,automaticPopup=-1;
__attribute__((used,noinline)) static void loadExtraSetting(void) {
 DWORD n=GetEnvironmentVariableA("LOCALAPPDATA",settingsPath,MAX_PATH);
 if(!n || n+32>=MAX_PATH)settingsPath[0]=0;
 else strcat(settingsPath,"\\NFSU2-NativeTrax.ini");
 for(int i=27;i<(int)trackCount;i++) {
  const char *key=packageConfig.tracks[i-27].key;
  unsigned mode=settingsPath[0]?GetPrivateProfileIntA("Native Trax",key,3,settingsPath):3;
  settings[i].mode=mode<=3?(BYTE)mode:3;
 }
}
__attribute__((used,noinline)) static void saveExtraSetting(void) {
 if(!settingsPath[0] || !validExtra(selected))return;
 char value[2]={(char)('0'+settings[selected].mode),0};
 const char *key=packageConfig.tracks[selected-27].key;
 if(!WritePrivateProfileStringA("Native Trax",key,value,settingsPath))logline("PREFERENCE write failed.");
}
static void __attribute__((fastcall)) applyPlaylist(void *player,void *unused,unsigned menu,unsigned race,int menus,int races,int shuffle) {
 (void)unused;
 /* Native storage contains only the original 27 songs. Never widen it. */
 ((void (__attribute__((thiscall)) *)(void*,unsigned,unsigned,int,int,int))0x46BAA0)(player,menu,race,menus,races,shuffle);
 for(int context=0;context<2;context++) {
  Playlist *list=&playlists[context];unsigned mask=context?race:menu;
  for(int i=0;i<(int)trackCount;i++) {
   int enabled=i<27?!!(mask&(1u<<i)):!!(settings[i].mode&(context?2:1));
   list->eligible[i]=list->remaining[i]=(BYTE)enabled;
  }
  list->last=-1;
 }
 playlistOwner=player;playlistReady=1;pendingAutomatic=automaticPopup=-1;
}
static int __attribute__((fastcall,noinline)) chooseTrack(void *self,void *unused) {
 (void)unused;pendingAutomatic=automaticPopup=-1;
 if(!self)return -1;
 BYTE *p=self,*manager=*(BYTE**)0x82B884;
 if(!manager)return -1;
 int garage=(*(int*)0x89E7B0==8);
 int menu=(*(int*)(manager+0x90)==1)||garage;
 if(menu && p[0xA5]!=1 && !garage)return -1;
 if(!playlistReady || playlistOwner!=self)
  applyPlaylist(self,0,*(unsigned*)(p+0x84),*(unsigned*)(p+0x8C),*(int*)(p+0x94),*(int*)(p+0x98),*(int*)(p+0x9C));
 Playlist *list=&playlists[menu?0:1];unsigned count=0;
 if(menu && nativeRequestPending && nativeRequestOwner==self) {
  for(int i=0;i<(int)trackCount;i++)list->remaining[i]=(BYTE)(i<27?!!(nativeRequestMask&(1u<<i)):0);
  list->last=-1;nativeRequestPending=0;
 }
 for(int i=0;i<(int)trackCount;i++)count+=list->remaining[i]!=0;
 if(!count) {
  for(int i=0;i<(int)trackCount;i++){list->remaining[i]=list->eligible[i];count+=list->remaining[i]!=0;}
  list->last=-1;
 }
 if(!count)return -1;
 int chosen=-1;
 if(*(int*)(p+0x9C)) {
  unsigned pick=((unsigned (__cdecl *)(unsigned))0x43C1C0)(count);
  if(pick>=count)return -1;
  for(int i=0;i<(int)trackCount;i++)if(list->remaining[i]){if(!pick){chosen=i;break;}pick--;}
 } else {
  Setting *native=(Setting*)0x83ACB8;
  for(int row=list->last+1;row<(int)trackCount;row++) {
   unsigned index=row<27?native[row].index:(unsigned)row;
   if(index<trackCount && list->remaining[index]){chosen=(int)index;list->last=row;break;}
  }
 }
 if(chosen<0)return -1;
 list->remaining[chosen]=0;
 /* Mirror only representable ORIGINAL remaining bits for other native readers. */
 unsigned nativeBag=0;for(int i=0;i<27;i++)if(list->remaining[i])nativeBag|=1u<<i;
 *(unsigned*)(p+(menu?0x88:0x90))=nativeBag;
 if(validExtra(chosen))pendingAutomatic=chosen;
 tracing=1;char text[120];snprintf(text,sizeof(text),"SELECT logical=%d context=%s",chosen,menu?"menu":"racing");logline(text);
 return validExtra(chosen)?0:chosen;
}
static void __cdecl showAutomatic(Metadata *entry) {
 int custom=automaticPopup;automaticPopup=-1;
 ((void (__cdecl *)(Metadata*))0x4AC9F0)(validExtra(custom)?&metadata[custom]:entry);
}
__attribute__((used)) static void *decoderTrampoline;
__attribute__((used,noinline)) static void traceDecoder(const unsigned *a) {
 if(tracing) {char text[180];snprintf(text,sizeof(text),"DECODER voice=%u codec=%u mode=%u channels/config=%u",a[0],a[1],a[2],a[3]);logline(text);}
}
__attribute__((naked)) static void decoderHook(void) {
 __asm__ volatile("pushfl\n pushal\n lea 40(%esp),%eax\n push %eax\n call _traceDecoder\n add $4,%esp\n popal\n popfl\n jmp *_decoderTrampoline");
}
static void logline(const char *s) {FILE *f=fopen(logpath,"a");if(f){fprintf(f,"%s\n",s);fclose(f);}}
__attribute__((used,noinline)) static void __cdecl prepareMenu(void) {
 memcpy(metadata,(void*)0x7ECD80,27*sizeof(Metadata));
 for(int i=0;i<27;i++)eventIds[i]=(unsigned)i;
 memcpy(settings,(void*)0x83ACB8,27*sizeof(Setting));
 for(int i=27;i<(int)trackCount;i++) {
  PackTrack *t=&packageConfig.tracks[i-27];
  metadata[i]=(Metadata){t->title,t->artist,t->album,"OF"};
  settings[i].index=(unsigned)i;eventIds[i]=79+(unsigned)(i-27);
 }
 logline("Native Trax metadata prepared.");
}
__attribute__((used,noinline)) static void __cdecl captureSelection(void *self) {
 void *row=*(void**)((BYTE*)self+0x70);
 selected=row?*(int*)((BYTE*)row+0x18):-1;
}
__attribute__((naked)) static void menuHook(void) {
 __asm__ volatile("pushfl\n pushal\n call _prepareMenu\n popal\n popfl\n jmp *_menuTrampoline");
}
__attribute__((naked)) static void callbackHook(void) {
 __asm__ volatile("pushfl\n pushal\n push %ecx\n call _captureSelection\n add $4,%esp\n popal\n popfl\n jmp *_callbackTrampoline");
}
static int dispatchLogged(unsigned handle,unsigned event,const char *origin) {
 int result=((int (__cdecl *)(unsigned,unsigned))0x7399E0)(handle,event);
 if(tracing) {char text[220];snprintf(text,sizeof(text),"EVENT origin=%s id=%u handle=%08x result=%d selected=%d custom=%d",origin,event,handle,result,selected,customPreview);logline(text);}
 return result;
}
__attribute__((used,noinline)) static int __cdecl routePreview(unsigned handle,unsigned event) {
 if(validExtra(customPreview))tracing=1;
 return dispatchLogged(handle,validExtra(customPreview)?eventIds[customPreview]:event,"preview");
}
static int __cdecl routeAutomatic(unsigned handle,unsigned event) {
 int custom=pendingAutomatic;pendingAutomatic=-1;automaticPopup=validExtra(custom)?custom:-1;
 return dispatchLogged(handle,validExtra(custom)?eventIds[custom]:event,"automatic");
}
static void __attribute__((fastcall,noinline)) previewTrack(void *player,void *unused,int index) {
 (void)unused;
 pendingAutomatic=-1;automaticPopup=-1;
 if(!player || index<0 || index>=(int)trackCount)return;
 tracing=1;
 int previous=customPreview;
 customPreview=validExtra(index)?index:-1;
 ((void (__attribute__((thiscall)) *)(void*,int))0x47AF90)(player,validExtra(customPreview)?0:index);
 customPreview=previous;
 if(validExtra(index))((void (__cdecl *)(Metadata*))0x4AC9F0)(&metadata[index]);
}
static int __cdecl routeStatus(unsigned handle,int *status) {
 int result=((int (__cdecl *)(unsigned,int*))0x739130)(handle,status);
 if(tracing && status==(int*)0x82AFB0) {
  static DWORD lastTick;
  static int lastNode=-999,lastRaw=-999,lastState=-999,lastFlags=-999;
  BYTE *manager=*(BYTE**)0x82B884;
  BYTE *player=manager?*(BYTE**)(manager+0xA0):0;
  int state=player?*(int*)(player+0xC0):-1;
  int flags=player?(player[0xA4]|player[0xA5]<<8|player[0xA6]<<16):-1;
  DWORD now=GetTickCount();
  if(status[0]!=lastNode || status[9]!=lastRaw || state!=lastState || flags!=lastFlags || now-lastTick>=10000) {
   char text[240];snprintf(text,sizeof(text),"STATUS result=%d node=%d raw24=%d raw08=%d raw0c=%d raw18=%d state=%d flags=%06x",result,status[0],status[9],status[2],status[3],status[6],state,flags);logline(text);
   lastTick=now;lastNode=status[0];lastRaw=status[9];lastState=state;lastFlags=flags;
  }
 }
 return result;
}
static void __attribute__((fastcall)) updateSettings(void *self,void *unused) {
 (void)unused;
 if(validExtra(selected))saveExtraSetting();
 memcpy((void*)0x83ACB8,settings,27*sizeof(Setting));
 ((void (__attribute__((thiscall)) *)(void*))0x479220)(self);
 if(tracing){char text[100];snprintf(text,sizeof(text),"SETTINGS changed row=%d mode=%u",selected,(selected>=0&&selected<(int)trackCount)?settings[selected].mode:255);logline(text);}
 if(selected>=0 && selected<(int)trackCount && settings[selected].mode!=0) {
  void *player=*(void**)((BYTE*)self+0xA0);
  if(player) {
   previewTrack(player,0,selected);
   logline("Enabled-row preview requested; original rows retain original event IDs.");
  } else logline("Row 28 changed: native player absent; preview skipped.");
 }
}
/* Optional policy: force native LONG only for plugin-owned metadata. */
__attribute__((used,noinline)) static void __attribute__((fastcall)) sizeAddedBanner(
 void *self,void *unused,const char *title,const char *artist,const char *album) {
 (void)unused;
 ((void (__attribute__((thiscall)) *)(void*,const char*,const char*,const char*))0x4AC7D0)(self,title,artist,album);
 if(!forceWideBanners)return;
 for(unsigned i=27;i<trackCount;i++) {
  if(title==metadata[i].title && artist==metadata[i].artist && album==metadata[i].album) {
   *(const char**)((BYTE*)self+0x58)=(const char*)0x790B50;
   *(const char**)((BYTE*)self+0x5C)=(const char*)0x790B48;
   return;
  }
 }
}

typedef struct {uintptr_t address; BYTE expected[8]; unsigned size; uintptr_t value; int relative;} Patch;
#include "patches.h"
__attribute__((used,noinline)) static void configurePatchCounts(void) {for(unsigned i=0;i<sizeof(patches)/sizeof(*patches);i++){if(patches[i].address==0x54BB38)patches[i].value=trackCount;if(patches[i].address==0x53DEE2)patches[i].value=trackCount*8;}}

static int writeBytes(uintptr_t a,const void *b,unsigned n) {
 DWORD old,ignored;if(!VirtualProtect((void*)a,n,PAGE_EXECUTE_READWRITE,&old))return 0;
 memcpy((void*)a,b,n);FlushInstructionCache(GetCurrentProcess(),(void*)a,n);
 VirtualProtect((void*)a,n,old,&ignored);return 1;
}
static void *trampoline(uintptr_t address,unsigned n) {
 BYTE *p=VirtualAlloc(0,n+5,MEM_COMMIT|MEM_RESERVE,PAGE_EXECUTE_READWRITE);
 if(!p)return 0;memcpy(p,(void*)address,n);p[n]=0xE9;
 *(int32_t*)(p+n+1)=(int32_t)(address+n-(uintptr_t)(p+n+5));return p;
}
static int verifyHash(const char *path,const BYTE expected[32]) {
 HCRYPTPROV prov=0;HCRYPTHASH hash=0;BYTE digest[32],buf[65536];DWORD got,len=32;int ok=0;
 HANDLE f=CreateFileA(path,GENERIC_READ,FILE_SHARE_READ,0,OPEN_EXISTING,0,0);
 if(f==INVALID_HANDLE_VALUE)return 0;
 if(CryptAcquireContextA(&prov,0,0,PROV_RSA_AES,CRYPT_VERIFYCONTEXT)&&CryptCreateHash(prov,CALG_SHA_256,0,0,&hash)) {
  int good=1;for(;;){if(!ReadFile(f,buf,sizeof(buf),&got,0)){good=0;break;}if(!got)break;if(!CryptHashData(hash,buf,got,0)){good=0;break;}}
  if(good&&CryptGetHashParam(hash,HP_HASHVAL,digest,&len,0))ok=!memcmp(expected,digest,32);
 }
 if(hash)CryptDestroyHash(hash);if(prov)CryptReleaseContext(prov,0);CloseHandle(f);return ok;
}
static int verifyFiles(void) {
 char path[MAX_PATH];
 static const BYTE exeHash[32]={0xf9,0xdd,0x86,0xc0,0x54,0x87,0x8c,0xe6,0x27,0x6b,0xeb,0x07,0xc1,0xfd,0x61,0x87,0x4f,0x7a,0x1e,0x4b,0xf1,0xf2,0x41,0xb0,0x84,0xc6,0x5b,0x73,0xe2,0x41,0x68,0xa7};

 if((uintptr_t)GetModuleHandleA(0)!=0x400000)return 0;
 DWORD n=GetModuleFileNameA(0,path,MAX_PATH);if(!n||n>=MAX_PATH||!verifyHash(path,exeHash))return 0;
 char *slash=strrchr(path,'\\');if(!slash||slash-path+16>=MAX_PATH)return 0;
 strcpy(slash+1,"SDATA\\sdat.viv");return verifyHash(path,packageConfig.archive);
}
BOOL WINAPI DllMain(HINSTANCE module,DWORD reason,LPVOID reserved) {
 (void)reserved;if(reason!=DLL_PROCESS_ATTACH)return TRUE;
 DisableThreadLibraryCalls(module);
 DWORD tempLen=GetTempPathA(MAX_PATH,logpath);if(tempLen&&tempLen+18<MAX_PATH)strcat(logpath,"NativeTrax.log");else strcpy(logpath,"NativeTrax.log");
 logline("Native Trax alpha loading.");
 if(!configurePackage()){logline("REFUSED: invalid package configuration.");return TRUE;}
 configurePatchCounts();
 if(!verifyFiles()){logline("REFUSED: executable or expanded archive SHA256/base mismatch. No patches applied.");return TRUE;}
 for(unsigned i=0;i<sizeof(patches)/sizeof(*patches);i++)if(memcmp((void*)patches[i].address,patches[i].expected,patches[i].size)) {
  logline("REFUSED: an in-memory patch site differs. No patches applied.");return TRUE;
 }
 menuTrampoline=trampoline(0x54B310,7);callbackTrampoline=trampoline(0x53DEB0,7);
 decoderTrampoline=trampoline(0x728DF9,6);
 if(!menuTrampoline||!callbackTrampoline||!decoderTrampoline){logline("REFUSED: trampoline allocation failed.");return TRUE;}
 loadExtraSetting();prepareMenu();
 for(unsigned i=0;i<sizeof(patches)/sizeof(*patches);i++) {
  Patch *p=&patches[i];BYTE replacement[8];memset(replacement,0x90,sizeof(replacement));
  if(p->relative){replacement[0]=(p->relative==2)?0xE8:0xE9;*(int32_t*)(replacement+1)=(int32_t)(p->value-(p->address+5));}
  else memcpy(replacement,&p->value,p->size);
  if(!writeBytes(p->address,replacement,p->size)) {
   for(unsigned j=0;j<i;j++)writeBytes(patches[j].address,patches[j].expected,patches[j].size);
   logline("REFUSED: patch write failed; preceding patches rolled back.");return TRUE;
  }
 }
 logline("Native Trax installed; original native layout retained.");return TRUE;
}

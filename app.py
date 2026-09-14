"""Native Trax alpha desktop patcher."""
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
import threading,queue,time,json,sys
import patcher
import diagnostics
import xt_workflow as workflow
COPY=json.loads((patcher.ASSETS/"ui-copy.json").read_text(encoding="utf-8"))
def ui(n):return COPY[f"{n:03d}"]

class GlassProgress(tk.Canvas):
 """Draw a blue glass highlight independently of the Windows widget theme."""
 def __init__(self,parent):
  super().__init__(parent,height=18,background='#202124',highlightthickness=0)
  self.value=0;self.mode='idle';self.phase=0;self.timer=None
  self.bind('<Configure>',lambda _:self.draw())
  self.bind('<Destroy>',self.stop)
 def stop(self,_=None):
  if self.timer is not None:self.after_cancel(self.timer);self.timer=None
 def set(self,mode,value=0):
  self.stop();self.mode=mode;self.value=max(0,min(1,value));self.phase=0;self.draw()
  if mode=='busy':self.tick()
 def tick(self):
  self.phase=(self.phase+0.025)%2;self.draw();self.timer=self.after(40,self.tick)
 def draw(self):
  self.delete('all');w=max(8,self.winfo_width());h=18
  self.create_rectangle(0,0,w-1,h-1,fill='#101820',outline='#536777')
  self.create_line(1,h-2,w-2,h-2,fill='#344650')
  width=w-4
  if self.mode=='busy':
   length=max(8,width*.23);position=1-abs(1-self.phase);left=2+(width-length)*position;right=left+length
  else:left=2;right=2+width*self.value
  if right<=left:return
  colors=['#c1efff','#a4e4ff','#8adaff','#70cdff','#56bfff','#3aadf5','#2095e5','#0876c9','#087dce','#1089d8','#1994e2','#25a0eb','#46b7f6','#78d5ff']
  for y,color in enumerate(colors,2):self.create_line(left,y,right,y,fill=color)
  self.create_line(left,2,left,15,fill='#9ce6ff');self.create_line(right,2,right,15,fill='#77cfff')

def center_dialog(dialog,parent):
 # Measure the complete dialog while withdrawn so it first appears over its owner.
 dialog.update_idletasks()
 x=parent.winfo_rootx()+(parent.winfo_width()-dialog.winfo_reqwidth())//2
 y=parent.winfo_rooty()+(parent.winfo_height()-dialog.winfo_reqheight())//2
 # A leading '+' preserves absolute negative coordinates on secondary monitors.
 dialog.geometry(f'+{x}+{y}')

def dark_theme(window):
 # Use a controllable ttk theme rather than Windows' light native widget colors.
 style=ttk.Style(window);style.theme_use('clam')
 bg='#202124';surface='#2b2d31';field='#17191c';fg='#eeeeef';muted='#999da5';accent='#365f91'
 window.configure(background=bg)
 window.option_add('*Toplevel.background',bg)
 style.configure('.',background=bg,foreground=fg,fieldbackground=field,troughcolor=field,bordercolor='#484b52',lightcolor=surface,darkcolor=surface)
 style.configure('TButton',background=surface,foreground=fg)
 style.map('TButton',background=[('disabled',bg),('pressed',accent),('active','#3b3e45')],foreground=[('disabled',muted)])
 style.configure('TEntry',fieldbackground=field,foreground=fg,insertcolor=fg)
 style.map('TEntry',fieldbackground=[('disabled',surface)],foreground=[('disabled',muted)])
 style.configure('Treeview',background=field,fieldbackground=field,foreground=fg)
 style.map('Treeview',background=[('selected',accent)],foreground=[('selected','#ffffff')])
 style.configure('Treeview.Heading',background=surface,foreground=fg)
 style.map('Treeview.Heading',background=[('active','#3b3e45')])
 style.configure('TCheckbutton',indicatorbackground=field,indicatorforeground=fg)
 style.map('TCheckbutton',background=[('active',bg)],foreground=[('disabled',muted)],indicatorbackground=[('disabled',surface),('selected',accent)])
 return style

def main():
 if sys.platform=='win32':
  import ctypes
  ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p('XtraTrax.Desktop'))
 window=tk.Tk();window.iconbitmap(default=str(patcher.ASSETS/'XtraTrax.ico'))
 dark_theme(window);window.title(ui(2).format(version=diagnostics.VERSION));window.geometry('850x700')
 window.minsize(780,600);frame=ttk.Frame(window,padding=16);frame.pack(fill='both',expand=True)
 game=tk.StringVar();status=tk.StringVar(value='');fields={k:tk.StringVar() for k in ['title','artist','album']}
 wide_banners=tk.BooleanVar(value=False);normalize=tk.BooleanVar(value=False)
 tracks=[];messages=queue.Queue();state={'busy':False,'package':None};buttons=[]
 ttk.Label(frame,text=ui(1),font=('Segoe UI',20,'bold')).pack(anchor='w')
 ttk.Label(frame,text=ui(3)).pack(anchor='w')
 ttk.Label(frame,text=ui(4)).pack(anchor='w',pady=(2,12))
 row=ttk.Frame(frame);row.pack(fill='x');game_entry=ttk.Entry(row,textvariable=game);game_entry.pack(side='left',fill='x',expand=True);buttons.append(game_entry)
 def choose_game():
  p=filedialog.askdirectory(title=ui(7))
  if p:game.set(p)
 game_button=ttk.Button(row,text=ui(6),command=choose_game);game_button.pack(side='left',padx=(8,0));buttons.append(game_button)
 detected=tk.StringVar(value=ui(41))
 ttk.Label(frame,textvariable=detected,wraplength=790).pack(anchor='w',pady=(6,0))
 detection={'generation':0,'timer':None}
 def detect_folder(path,generation):
  try:
   result=patcher.detect_game(path)
   text=ui(43).format(build=result['label'],layout=result['layout'])
   if result['supported']:text+=ui(44)
   else:text+=' · Installation unavailable'
  except (OSError,ValueError):text=ui(46)
  messages.put(('detected',generation,text))
 def folder_changed(*_):
  state['package']=None
  detection['generation']+=1;generation=detection['generation']
  if detection['timer'] is not None:window.after_cancel(detection['timer']);detection['timer']=None
  path=game.get().strip()
  if not path:detected.set(ui(41));return
  detected.set(ui(42))
  detection['timer']=window.after(300,lambda:threading.Thread(target=detect_folder,args=(path,generation),daemon=True).start())
 game.trace_add('write',folder_changed)
 list_frame=ttk.Frame(frame);list_frame.pack(fill='both',expand=True,pady=10)
 listing=ttk.Treeview(list_frame,columns=('title','artist','album'),show='headings',selectmode='extended',height=9)
 for col,n in [('title',12),('artist',13),('album',14)]:listing.heading(col,text=ui(n));listing.column(col,width=230,minwidth=100)
 scrollbar=ttk.Scrollbar(list_frame,orient='vertical',command=listing.yview)
 listing.configure(yscrollcommand=scrollbar.set)
 scrollbar.pack(side='right',fill='y');listing.pack(side='left',fill='both',expand=True)
 def select_all(_=None):
  if not state['busy']:listing.selection_set(listing.get_children())
  return 'break'
 listing.bind('<Control-a>',select_all);listing.bind('<Control-A>',select_all)
 def selected():return tuple(int(i) for i in listing.selection())
 def refresh():
  listing.delete(*listing.get_children())
  for i,t in enumerate(tracks):listing.insert('', 'end',iid=str(i),values=(t['title'],t['artist'],t['album']))
  state['package']=None
 def select(_=None):
  if len(selected())==1:
   for k in fields:fields[k].set(tracks[selected()[0]][k])
 listing.bind('<<TreeviewSelect>>',select)
 def add(paths):
  try:
   patcher.check(len(tracks)+len(paths)<=patcher.MAX_ADDED,'Maximum 100 additions.')
   pending=[]
   for p in paths:
    patcher.inspect_audio(p);pending.append(dict(path=p,title=Path(p).stem,artist='',album=''))
   tracks.extend(pending);refresh()
  except Exception as e:messagebox.showerror(ui(38),str(e))
 def add_demo():
  add([str(patcher.ASSETS/'Dead at Dawn.mp3')])
  if tracks and tracks[-1]['path']==str(patcher.ASSETS/'Dead at Dawn.mp3'):
   tracks[-1].update(title=ui(22),artist=ui(23),album=ui(24));refresh()
 def remove():
  for i in sorted(selected(),reverse=True):tracks.pop(i)
  refresh()
 controls=ttk.Frame(frame);controls.pack(fill='x')
 for text,fn in [(ui(8),lambda:add(filedialog.askopenfilenames(filetypes=[(ui(9),'*.wav *.flac *.m4a *.mp3 *.ogg')]))),(ui(10),add_demo),('Select All',select_all),(ui(11),remove)]:
  b=ttk.Button(controls,text=text,command=fn);b.pack(side='left',padx=(0,8));buttons.append(b)
 for k in fields:
  r=ttk.Frame(frame);r.pack(fill='x',pady=3);ttk.Label(r,text=ui({'title':12,'artist':13,'album':14}[k]),width=8).pack(side='left');entry=ttk.Entry(r,textvariable=fields[k]);entry.pack(fill='x',expand=True);buttons.append(entry)
 def apply_fields():
  if len(selected())==1:
   i=selected()[0]
   try:
    for k in fields:patcher.text_bytes(fields[k].get())
    patcher.check(fields['title'].get().strip(),'Title cannot be blank.')
    tracks[i].update({k:v.get() for k,v in fields.items()});refresh();listing.selection_set(str(i))
   except Exception as e:messagebox.showerror(ui(39),str(e));return False
  return True
 b=ttk.Button(frame,text=ui(15),command=apply_fields);b.pack(anchor='e');buttons.append(b)
 ttk.Label(frame,text=ui(16)).pack(anchor='w',pady=6)
 def banner_changed():
  state['package']=None
 b=ttk.Checkbutton(frame,text=ui(17),variable=wide_banners,command=banner_changed)
 b.pack(anchor='w');buttons.append(b)
 ttk.Style(window).configure('Volume.TCheckbutton',wraplength=760)
 b=ttk.Checkbutton(frame,text='Attempt to match UG2 OST Volume (This will significantly increase patching time, and may compromise audio quality of imported songs)',variable=normalize,style='Volume.TCheckbutton')
 b.pack(anchor='w');buttons.append(b)
 def work(fn,done):
  if state['busy']:return
  state['busy']=True
  progress_bar.set('busy')
  for b in buttons:b.state(['disabled'])
  def runner():
   try:result=fn();messages.put(('done',done,result))
   except Exception as e:messages.put(('error',diagnostics.describe(e)))
  threading.Thread(target=runner,daemon=False).start()
 def confirm_replace():
  result=[False];dialog=tk.Toplevel(window);dialog.withdraw();dialog.title(ui(25));dialog.transient(window);dialog.resizable(False,False)
  ttk.Label(dialog,text=ui(26),wraplength=480,padding=20).pack()
  row=ttk.Frame(dialog,padding=(20,0,20,20));row.pack(fill='x')
  def finish(value):result[0]=value;dialog.destroy()
  ttk.Button(row,text=ui(28),command=lambda:finish(False)).pack(side='right',padx=5)
  ttk.Button(row,text=ui(27),command=lambda:finish(True)).pack(side='right',padx=5)
  dialog.protocol('WM_DELETE_WINDOW',lambda:finish(False));dialog.bind('<Escape>',lambda _:finish(False))
  center_dialog(dialog,window);dialog.deiconify();dialog.grab_set();window.wait_window(dialog)
  return result[0]
 def apply():
  if state['busy'] or not apply_fields():return
  gamepath=game.get()
  if workflow.has_installation(gamepath) and not confirm_replace():return
  snapshot=[dict(x,normalize=normalize.get(),limiting=normalize.get()) for x in tracks];wide=wide_banners.get()
  def progress(text):
   match=__import__('re').match(r'Encoding (\d+)/(\d+): (.*)',text)
   fraction=None
   if match:
    fraction=(int(match[1])-1)/max(1,int(match[2]))
    text=ui(29).format(current=match[1],total=match[2],title=match[3])
   messages.put(('status',text,fraction))
  work(lambda:workflow.apply(gamepath,snapshot,wide,progress),lambda _:status.set(ui(33)))
 def restore():
  gamepath=game.get();status.set(ui(32));work(lambda:workflow.restore(gamepath),lambda _:status.set(ui(34)))
 row=ttk.Frame(frame);row.pack(fill='x',pady=12)
 for text,fn in [(ui(19),apply),(ui(20),restore)]:
  b=ttk.Button(row,text=text,command=fn);b.pack(side='left',padx=(0,8));buttons.append(b)
 progress_bar=GlassProgress(frame);progress_bar.pack(fill='x',pady=(0,4))
 status_label=ttk.Label(frame,textvariable=status,wraplength=790)
 def show_status(*_):
  if status.get():status_label.pack(anchor='w',pady=10)
  else:status_label.pack_forget()
 status.trace_add('write',show_status)
 def poll():
  while not messages.empty():
   item=messages.get()
   if item[0]=='detected':
    if item[1]==detection['generation']:detected.set(item[2])
    continue
   if item[0]=='status':
    status.set(item[1]);progress_bar.set('busy' if item[2] is None else 'progress',item[2] or 0);continue
   state['busy']=False
   for b in buttons:b.state(['!disabled'])
   if item[0]=='done':progress_bar.set('progress',1);item[1](item[2])
   else:progress_bar.set('idle');status.set(ui(35).format(error=item[1]));messagebox.showerror(ui(1),item[1])
  window.after(100,poll)
 def close():
  if state['busy']:messagebox.showinfo(ui(36),ui(37))
  else:window.destroy()
 def fit_minimum():
  # Measure after Tk resolves fonts, DPI and wrapped text; fixed pixel limits
  # can otherwise let pack clip the controls below the song list.
  window.update_idletasks()
  window.minsize(max(780,frame.winfo_reqwidth()),max(600,frame.winfo_reqheight()))
 for variable in (status,detected):
  variable.trace_add('write',lambda *_:window.after_idle(fit_minimum))
 window.protocol('WM_DELETE_WINDOW',close);fit_minimum();poll();window.mainloop()

if __name__=='__main__':
 if '--self-test' in sys.argv:
  result={'lgu_template':(patcher.ASSETS/'lgu/NativeTrax.template').is_file(),'assets':patcher.ASSETS.is_dir(),'template':(patcher.ASSETS/'NativeTrax.template').is_file(),'demo':patcher.inspect_audio(patcher.ASSETS/'Dead at Dawn.mp3').frames}
  if len(sys.argv)>2:Path(sys.argv[2]).write_text(json.dumps(result))
  print(json.dumps(result))
 elif '--encode-audio-test' in sys.argv:
  result=patcher.encode(dict(path=sys.argv[2],title='Test',artist='',album='',normalize='--normalize' in sys.argv,limiting='--limiting' in sys.argv),sys.argv[3])
  Path(sys.argv[4]).write_text(json.dumps(result),encoding='utf-8')
 elif '--build-demo-test' in sys.argv:
  demo=dict(path=str(patcher.ASSETS/'Dead at Dawn.mp3'),title=ui(22),artist=ui(23),album=ui(24))
  patcher.build(sys.argv[2],[demo],sys.argv[3])
 else:main()


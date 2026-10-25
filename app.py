import os,json,secrets,hashlib,csv,io
from datetime import datetime,timezone,timedelta
from functools import wraps
from flask import Flask,request,redirect,url_for,session,render_template,flash,send_file,abort
from werkzeug.utils import secure_filename
app=Flask(__name__); app.secret_key=os.getenv("APP_SECRET","change-this-secret")
PASSWORD=os.getenv("ADMIN_PASSWORD","change-me")
DATA="data"; UP=os.path.join(DATA,"uploads"); DB=os.path.join(DATA,"sessions.json")
os.makedirs(UP,exist_ok=True)
TERMS=["EULEN","Menyo","Tiago","FalloutMenu","CobraMenu","DOPAMINE MENU","Phantom","ZENTRIX","vMenu","KekHack","RedEngine","Mod Menu","hack_fivem","fivem esp","wallhack","injector","Lua Executor","GH Injector","Extreme Injector","Winject","CheatEngine","UnknownCheats","DUMPER","DECRYPTER","BYPASS","RESOURCE BLOCKER","RXEXV3","No_Recoil.rpf","aML.lua","pedaccuracy.meta","weaponcomponents.meta","weaponanimation.meta","bsk_skills.rpf","quickEnter.rpf"]
def dbread():
 try:
  with open(DB,encoding="utf-8") as f:return json.load(f)
 except:return {"sessions":[]}
def dbwrite(d):
 with open(DB,"w",encoding="utf-8") as f:json.dump(d,f,ensure_ascii=False,indent=2)
def admin(fn):
 @wraps(fn)
 def w(*a,**k):
  if not session.get("admin"):return redirect(url_for("login"))
  return fn(*a,**k)
 return w
@app.route("/")
@admin
def home():
 ss=sorted(dbread()["sessions"],key=lambda x:x["created"],reverse=True)
 return render_template("dashboard.html",ss=ss)
@app.route("/login",methods=["GET","POST"])
def login():
 if request.method=="POST":
  if secrets.compare_digest(request.form.get("password",""),PASSWORD):session["admin"]=True;return redirect("/")
  flash("كلمة المرور غير صحيحة")
 return render_template("login.html")
@app.route("/logout")
def logout():session.clear();return redirect("/login")
@app.route("/create",methods=["POST"])
@admin
def create():
 player=request.form.get("player","").strip()[:100]
 if not player:flash("اكتب اسم اللاعب");return redirect("/")
 mins=max(5,min(int(request.form.get("minutes",10)),1440)); token=secrets.token_urlsafe(24)
 x={"id":secrets.token_hex(5),"token":token,"player":player,"created":datetime.now(timezone.utc).isoformat(),"expires":(datetime.now(timezone.utc)+timedelta(minutes=mins)).isoformat(),"status":"بانتظار الملفات","results":[]}
 d=dbread();d["sessions"].append(x);dbwrite(d);return redirect(url_for("detail",sid=x["id"]))
@app.route("/session/<sid>")
@admin
def detail(sid):
 x=next((x for x in dbread()["sessions"] if x["id"]==sid),None)
 if not x:abort(404)
 return render_template("session.html",x=x,up=url_for("upload",token=x["token"],_external=True))
@app.route("/upload/<token>",methods=["GET","POST"])
def upload(token):
 d=dbread();x=next((x for x in d["sessions"] if secrets.compare_digest(x["token"],token)),None)
 if not x:abort(404)
 if datetime.fromisoformat(x["expires"])<datetime.now(timezone.utc):return "انتهت صلاحية الرابط",410
 if request.method=="POST":
  fs=[f for f in request.files.getlist("files") if f and f.filename]
  if not fs:flash("اختر ملفات");return redirect(request.url)
  folder=os.path.join(UP,x["id"]);os.makedirs(folder,exist_ok=True)
  for f in fs[:200]:
   name=secure_filename(f.filename) or "upload.bin"; path=os.path.join(folder,secrets.token_hex(4)+"_"+name);h=hashlib.sha256();size=0
   with open(path,"wb") as o:
    while True:
     b=f.stream.read(1024*1024)
     if not b:break
     size+=len(b);h.update(b);o.write(b)
   hits=[t for t in TERMS if t.lower() in name.lower()]
   x["results"].append({"file":name,"size":size,"sha256":h.hexdigest(),"hits":hits})
  x["status"]="اكتمل الرفع";dbwrite(d);flash("تم تحليل أسماء الملفات");return redirect(request.url)
 return render_template("upload.html",x=x)
@app.route("/report/<sid>.csv")
@admin
def report(sid):
 x=next((x for x in dbread()["sessions"] if x["id"]==sid),None)
 if not x:abort(404)
 s=io.StringIO();w=csv.writer(s);w.writerow(["Player","Filename","SizeBytes","SHA256","Indicators","Disclaimer"])
 for r in x["results"]:w.writerow([x["player"],r["file"],r["size"],r["sha256"],"; ".join(r["hits"]),"Filename indicator only; not proof"])
 return send_file(io.BytesIO(s.getvalue().encode("utf-8-sig")),mimetype="text/csv",as_attachment=True,download_name="3eN_report.csv")
@app.route("/health")
def health():return {"ok":True}

#!/usr/bin/env python3
"""Web-based YOLO bounding box annotator for freediver labeling.

Usage:
  python tools/annotator_web.py --input data/raw/images/ --output data/raw/labels/
  Then open http://localhost:8765
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path.cwd()), **kwargs)

    def do_GET(self):
        if self.path == "/api/frames":
            img_dir = Path(self.server.img_dir)
            images = sorted(img_dir.glob("*.jpg"))
            lbl_dir = Path(self.server.label_dir)
            data = []
            for i, p in enumerate(images):
                label_file = lbl_dir / f"{p.stem}.txt"
                boxes = []
                if label_file.exists():
                    for line in label_file.read_text().strip().split("\n"):
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            boxes.append([float(x) for x in parts[1:5]])
                data.append({
                    "id": i, "filename": p.name, "boxes": boxes,
                    "total": len(images),
                })
            self._json(data)
        elif self.path.startswith("/img/"):
            # Serve image from input directory
            filename = unquote(self.path[5:])  # strip "/img/"
            img_path = Path(self.server.img_dir) / filename
            if img_path.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(img_path.stat().st_size))
                self.end_headers()
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, f"Not found: {filename}")
        elif self.path == "/" or self.path == "/index.html":
            self._html()
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/save":
            length = int(self.headers.get("content-length", 0))
            body = json.loads(self.rfile.read(length))
            filename = body["filename"]
            boxes = body["boxes"]
            lbl_dir = Path(self.server.label_dir)
            lbl_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(filename).stem
            lbl_path = lbl_dir / f"{stem}.txt"
            lines = [f"0 {bx:.6f} {by:.6f} {bw:.6f} {bh:.6f}" for bx, by, bw, bh in boxes]
            lbl_path.write_text("\n".join(lines))
            self._json({"ok": True, "count": len(boxes)})
        else:
            self.send_error(404)

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self):
        html = r"""<!DOCTYPE html>
<html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Freediver Annotator</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#1a1a2e;color:#e0e0e0;font-family:system-ui;display:flex;flex-direction:column;height:100vh}
#toolbar{display:flex;align-items:center;gap:12px;padding:8px 12px;background:#12121e;border-bottom:1px solid #333;flex-shrink:0}
#toolbar button{padding:6px 16px;border:1px solid #444;background:#2a2a3a;color:#e0e0e0;border-radius:4px;cursor:pointer;font-size:14px}
#toolbar button:hover{background:#3a3a5a}
#toolbar button:disabled{opacity:0.4;cursor:default}
#toolbar select{padding:6px 8px;background:#2a2a3a;color:#e0e0e0;border:1px solid #444;border-radius:4px;font-size:14px;max-width:300px}
#counter{font-size:13px;color:#888;min-width:100px}
#main{display:flex;flex:1;overflow:hidden}
#canvas-container{flex:1;display:flex;align-items:center;justify-content:center;background:#0a0a14;position:relative}
canvas{cursor:crosshair}
#sidebar{width:260px;background:#12121e;padding:12px;overflow-y:auto;border-left:1px solid #333;flex-shrink:0}
#sidebar h3{font-size:13px;color:#8888cc;margin-bottom:8px}
.box-entry{display:flex;gap:8px;font-size:12px;padding:4px 6px;margin:2px 0;background:#1a1a2e;border-radius:3px;font-family:monospace}
.box-entry .del-btn{color:#ff6666;cursor:pointer;font-weight:bold}
.shortcuts{font-size:11px;color:#666;margin-top:16px;line-height:1.8}
.shortcuts kbd{background:#2a2a3a;padding:1px 5px;border-radius:2px;font-size:10px;border:1px solid #444}
.status{font-size:12px;color:#88cc88;margin-top:8px}
</style></head><body>
<div id="toolbar">
  <button id="prevBtn" onclick="navigate(-1)">◀ 上一张</button>
  <select id="jumpSelect" onchange="jumpTo(this.value)"></select>
  <button id="nextBtn" onclick="navigate(1)">下一张 ▶</button>
  <span id="counter"></span>
  <button onclick="deleteBox()">✕ 删框</button>
  <button onclick="clearBoxes()">清除全部</button>
  <button onclick="saveCurrent()" style="background:#335533;border-color:#558855;">💾 保存</button>
  <span id="status" class="status"></span>
</div>
<div id="main">
  <div id="canvas-container"><canvas id="canvas"></canvas></div>
  <div id="sidebar">
    <h3>标注框 (YOLO格式)</h3>
    <div id="boxList">—</div>
    <div class="shortcuts">
      <kbd>N</kbd> 下一张 &nbsp; <kbd>P</kbd> 上一张<br>
      <kbd>D</kbd> 删框 &nbsp; <kbd>S</kbd> 保存<br>
      鼠标拖动画框<br>
      绿色框 = 已预标注
    </div>
  </div>
</div>
<script>
let frames=[],currentIdx=0,boxes=[],drawing=false,startX=0,startY=0,baseImage=null;

async function loadFrames(){
  const res=await fetch('/api/frames');
  frames=await res.json();
  let sel=document.getElementById('jumpSelect');
  sel.innerHTML=frames.map((f,i)=>{
    let h=f.boxes.length>0?'✓ ':'';
    return '<option value="'+i+'">'+h+f.filename+'</option>';
  }).join('');
  loadFrame(0);
}

function loadFrame(idx){
  currentIdx=idx;
  let f=frames[idx];
  boxes=[...f.boxes];
  baseImage=new Image();
  baseImage.onload=()=>{
    let c=document.getElementById('canvas');
    let container=document.getElementById('canvas-container');
    let s=Math.min(container.clientWidth/baseImage.naturalWidth,container.clientHeight/baseImage.naturalHeight,1.8);
    c.width=baseImage.naturalWidth*s;
    c.height=baseImage.naturalHeight*s;
    repaint();
  };
  baseImage.src='/img/'+encodeURIComponent(f.filename);
}

function repaint(){
  let c=document.getElementById('canvas');
  let ctx=c.getContext('2d');
  ctx.clearRect(0,0,c.width,c.height);
  if(baseImage) ctx.drawImage(baseImage,0,0,c.width,c.height);
  for(let [bx,by,bw,bh] of boxes){
    let w=bw*c.width, h=bh*c.height;
    let x=(bx-bw/2)*c.width, y=(by-bh/2)*c.height;
    ctx.strokeStyle='#00ff66'; ctx.lineWidth=2;
    ctx.strokeRect(x,y,w,h);
    ctx.fillStyle='rgba(0,255,100,0.15)';
    ctx.fillRect(x,y,w,h);
  }
  updateUI();
  updateBoxList();
}

function updateUI(){
  let f=frames[currentIdx];
  document.getElementById('counter').textContent=(currentIdx+1)+' / '+f.total;
  document.getElementById('jumpSelect').value=currentIdx;
  document.getElementById('prevBtn').disabled=currentIdx<=0;
  document.getElementById('nextBtn').disabled=currentIdx>=f.total-1;
}

function updateBoxList(){
  let div=document.getElementById('boxList');
  if(boxes.length===0){div.innerHTML='<span style="color:#666">无标注框</span>';return}
  div.innerHTML=boxes.map((b,i)=>
    '<div class="box-entry">'+(i+1)+'. cx='+b[0].toFixed(3)+' cy='+b[1].toFixed(3)+' w='+b[2].toFixed(3)+' h='+b[3].toFixed(3)+' <span class="del-btn" onclick="deleteBoxAt('+i+')">✕</span></div>'
  ).join('');
}

let canvas=document.getElementById('canvas');
canvas.addEventListener('mousedown',e=>{drawing=true;startX=e.offsetX;startY=e.offsetY});
canvas.addEventListener('mousemove',e=>{
  if(!drawing)return;
  let ctx=canvas.getContext('2d');
  repaint();
  ctx.strokeStyle='#ffcc00';ctx.lineWidth=2;ctx.setLineDash([4,4]);
  ctx.strokeRect(startX,startY,e.offsetX-startX,e.offsetY-startY);
  ctx.setLineDash([]);
});
canvas.addEventListener('mouseup',e=>{
  if(!drawing)return; drawing=false;
  let x1=Math.min(startX,e.offsetX), y1=Math.min(startY,e.offsetY);
  let x2=Math.max(startX,e.offsetX), y2=Math.max(startY,e.offsetY);
  if(x2-x1<5||y2-y1<5){repaint();return}
  let cx=((x1+x2)/2)/canvas.width, cy=((y1+y2)/2)/canvas.height;
  let bw=(x2-x1)/canvas.width, bh=(y2-y1)/canvas.height;
  boxes.push([cx,cy,bw,bh]);
  repaint();
});

function navigate(dir){saveCurrent().then(()=>{let i=currentIdx+dir;if(i>=0&&i<frames.length)loadFrame(i)})}
function jumpTo(v){saveCurrent().then(()=>loadFrame(parseInt(v)))}
function deleteBox(){if(boxes.length){boxes.pop();repaint()}}
function deleteBoxAt(i){boxes.splice(i,1);repaint()}
function clearBoxes(){boxes=[];repaint()}
async function saveCurrent(){
  let f=frames[currentIdx]; if(!f)return;
  try{
    let res=await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:f.filename,boxes:boxes})});
    let d=await res.json();
    document.getElementById('status').textContent='✓ 已保存 '+d.count+' 框';
    f.boxes=[...boxes];
    let sel=document.getElementById('jumpSelect');
    sel.innerHTML=frames.map((f,i)=>{let h=f.boxes.length>0?'✓ ':'';return '<option value="'+i+'">'+h+f.filename+'</option>'}).join('');
    setTimeout(()=>{document.getElementById('status').textContent=''},1500);
  }catch(e){document.getElementById('status').textContent='保存失败'}
}
document.addEventListener('keydown',e=>{
  if(e.key==='n'||e.key==='N')navigate(1);
  if(e.key==='p'||e.key==='P')navigate(-1);
  if(e.key==='d'||e.key==='D')deleteBox();
  if(e.key==='s'||e.key==='S')saveCurrent();
});
loadFrames();
</script></body></html>"""
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Web-based YOLO annotator")
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--port", "-p", type=int, default=8765)
    args = parser.parse_args()

    img_dir = str(Path(args.input).resolve())
    lbl_dir = str(Path(args.output).resolve())
    Path(lbl_dir).mkdir(parents=True, exist_ok=True)

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    server.img_dir = img_dir
    server.label_dir = lbl_dir

    print(f"http://localhost:{args.port}")
    print(f"Images: {img_dir} ({len(list(Path(img_dir).glob('*.jpg')))} frames)")
    print(f"Labels: {lbl_dir}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDone")


if __name__ == "__main__":
    main()

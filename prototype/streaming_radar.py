import asyncio, collections, json, os, time, urllib.request
import websockets
KEY=os.environ.get("FINNHUB_API_KEY","")
TOPIC=os.environ.get("NTFY_URL","")
SYMBOLS=[x.strip().upper() for x in os.environ.get("SYMBOLS","NVDA,TSLA,RKLB").split(",") if x.strip()]
RULES=[(300,2),(600,4),(300,-2),(600,-4)]

async def main():
 if not KEY: raise SystemExit("FINNHUB_API_KEY fehlt")
 history=collections.defaultdict(collections.deque)
 last={}
 while True:
  try:
   async with websockets.connect("wss://ws.finnhub.io?token="+KEY,ping_interval=20) as ws:
    for symbol in SYMBOLS: await ws.send(json.dumps({"type":"subscribe","symbol":symbol}))
    async for raw in ws:
     msg=json.loads(raw)
     if msg.get("type")!="trade": continue
     for trade in msg.get("data",[]):
      s,p,t=trade["s"],float(trade["p"]),int(trade["t"])/1000
      if p<=0: continue
      q=history[s]
      if q and t<q[-1][0]: continue
      q.append((t,p))
      while q and t-q[0][0]>610:q.popleft()
      if len(q)<3:continue
      for window,threshold in RULES:
       base=next(((ts,pr) for ts,pr in q if t-ts<=window),None)
       if not base or t-base[0]<30:continue
       change=(p/base[1]-1)*100
       hit=change>=threshold if threshold>0 else change<=threshold
       k=(s,window,threshold)
       if hit and t-last.get(k,-1e20)>900:
        last[k]=t
        body=f"{s}: {change:+.2f}% in {window//60}min; last trade {p:g}"
        print(body,flush=True)
        if TOPIC:
         def push():
          req=urllib.request.Request(TOPIC,data=body.encode(),headers={"Title":"Market Radar "+s,"Priority":"high"},method="POST")
          with urllib.request.urlopen(req,timeout=8) as response:response.read()
         try:await asyncio.to_thread(push)
         except Exception as ex:print("Push error",ex,flush=True)
  except Exception as ex:
   print("Reconnect in 10s:",ex,flush=True)
   await asyncio.sleep(10)

if __name__=="__main__":asyncio.run(main())

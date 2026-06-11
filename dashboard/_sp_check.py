import sys, json, traceback
sys.path.insert(0, r"C:\Users\integ\Documents\Claude\Projects\ShipStack\dashboard")
OUT = r"C:\Users\integ\Documents\Claude\Projects\ShipStack\dashboard\_sp_out.txt"
try:
    import social_push
    r = {"drivers": list(social_push.DRIVERS.keys()),
         "n_status": len(social_push.platforms_status()),
         "queue_len": len(social_push.list_queue())}
    open(OUT,"w",encoding="utf-8").write(json.dumps(r, indent=2))
except Exception:
    open(OUT,"w",encoding="utf-8").write(traceback.format_exc())
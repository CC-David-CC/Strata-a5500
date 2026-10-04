CONFIG_SHA='38d6c62951f5bea41ae9f081b771776e3295c5f6e7c3367341f40a6a358d10cd'
ENGINE_SHA='95290a8a30c5d8d8984b02b5b7fc3128c8d2745f139891e5bdb9a5a9b5e6a7b9'
import fcntl, hashlib, json, os, pathlib, sys
config = pathlib.Path(__file__).with_name("config.json")
if not os.environ.get("STRATA_API_KEY", "").strip():
    raise SystemExit("Refusing LAN startup without an API key")
if hashlib.sha256(config.read_bytes()).hexdigest() != CONFIG_SHA:
    raise SystemExit("Frozen configuration changed; review it before updating its checksum")
cfg = json.loads(config.read_text())
if hashlib.sha256(pathlib.Path(cfg["exe"]).read_bytes()).hexdigest() != ENGINE_SHA:
    raise SystemExit("Frozen engine checksum mismatch")
lock = os.open(str(pathlib.Path.home()/"fleet-downloads/.rtxpro-bandwidth.lock"), os.O_RDWR|os.O_CREAT, 0o600)
fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
os.set_inheritable(lock, True)
os.chdir(cfg["cwd"])
os.execv(sys.executable, [sys.executable, "-u", "-m", "serve.server", "--engine", "strata", "--config", str(config), "--host", "10.0.7.68", "--port", "8095"])

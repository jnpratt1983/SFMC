import importlib.util, sys
spec = importlib.util.spec_from_file_location("lw", "/Users/jennifer.pratt/Desktop/c360-sfdx/scripts/lifecycle_watch.py")
lw = importlib.util.module_from_spec(spec); spec.loader.exec_module(lw)
MC, simple, complex_, strip = lw.MC, lw.simple, lw.complex_, lw.strip
def client():
    m = MC(lw.load_env()); m.auth(); return m

import uvloop
from mahiru.mahiru import Mahiru

if __name__ == "__main__":
    uvloop.install()
    Mahiru().run()

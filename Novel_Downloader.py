from gui import NovelDownloaderApp
import tkinter as tk
from controller import Controller

if __name__ == "__main__":
    root = tk.Tk()
    app = NovelDownloaderApp(root)
    controller = Controller(app)
    root.mainloop()
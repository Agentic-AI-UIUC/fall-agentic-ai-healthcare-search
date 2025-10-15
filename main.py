from pynput.keyboard import Key, Listener
from scraper import Scraper

scraper = Scraper(
    base_url="https://www.msdmanuals.com",
    first_url="professional/psychiatric-disorders/mood-disorders/depressive-disorders",
    source="MSD Manual",
)

def on_press(key):
    if key == Key.esc:
        scraper.set_stop()

listener = Listener(on_press=on_press)
listener.start()

scraper.mainloop()

listener.stop()
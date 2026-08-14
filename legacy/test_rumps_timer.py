import rumps
import time

class TestApp(rumps.App):
    def __init__(self):
        super(TestApp, self).__init__("TestApp")
        self.menu = ["Test Delay"]

    @rumps.clicked("Test Delay")
    def test_delay(self, _):
        print(f"[{time.time()}] Button clicked! Starting timer for 2 seconds...")
        
        def delayed_close(sender):
            if not hasattr(sender, 'tick_count'):
                sender.tick_count = 0
            sender.tick_count += 1
            print(f"[{time.time()}] Timer tick {sender.tick_count}")
            if sender.tick_count > 2:
                print(f"[{time.time()}] Closing now!")
                sender.stop()

        # create a local variable close_timer
        close_timer = rumps.Timer(delayed_close, 1)
        close_timer.start()

if __name__ == "__main__":
    app = TestApp()
    # Simulate a click after 1 second
    import threading
    def click_it():
        time.sleep(1)
        app.test_delay(None)
    threading.Thread(target=click_it).start()
    
    # run for a few seconds then quit
    def quit_app():
        time.sleep(5)
        rumps.quit_application()
    threading.Thread(target=quit_app).start()
    
    app.run()

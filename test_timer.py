import rumps
from AppKit import NSPanel

class TestApp(rumps.App):
    def __init__(self):
        super(TestApp, self).__init__("TestApp")
        self.menu = ["Test"]

    @rumps.clicked("Test")
    def test_timer(self, _):
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((100, 100), (200, 200)), 1, 2, False
        )
        panel.makeKeyAndOrderFront_(None)
        self.panel = panel
        
        # Test if this crashes or fires instantly
        timer = rumps.Timer(self._close, 2)
        timer.start()

    def _close(self, sender=None):
        print(f"_close called with {sender}")
        if sender:
            sender.stop()
        if self.panel:
            self.panel.close()
            self.panel = None

if __name__ == "__main__":
    TestApp().run()

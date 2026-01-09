from datetime import datetime

class Logger():
    def __init__(self, class_name: str):
        self.class_name = class_name

    def log(self, message):
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"[{current_time}] {self.class_name} - {message}")
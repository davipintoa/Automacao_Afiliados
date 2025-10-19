import pyautogui
import time

time.sleep(2)
x, y = pyautogui.position()
print(f"Mouse position after 2 seconds: ({x}, {y})")

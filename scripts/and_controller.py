import os
import subprocess
import xml.etree.ElementTree as ET

from config import load_config
from utils import print_with_color


configs = load_config()


class AndroidElement:
    def __init__(self, uid, bbox, attrib):
        self.uid = uid
        self.bbox = bbox
        self.attrib = attrib


def execute_adb(adb_command):
    # print(adb_command)
    result = subprocess.run(adb_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    print_with_color(f"Command execution failed: {adb_command}", "red")
    print_with_color(result.stderr, "red")
    return "ERROR"


def list_all_devices():
    adb_command = "adb devices"
    device_list = []
    result = execute_adb(adb_command)
    if result != "ERROR":
        devices = result.split("\n")[1:]
        device_list.extend(d.split()[0] for d in devices)
    return device_list


def get_id_from_element(elem):
    bounds = elem.attrib["bounds"][1:-1].split("][")
    x1, y1 = map(int, bounds[0].split(","))
    x2, y2 = map(int, bounds[1].split(","))
    elem_w, elem_h = x2 - x1, y2 - y1
    if "resource-id" in elem.attrib and elem.attrib["resource-id"]:
        elem_id = elem.attrib["resource-id"].replace(":", ".").replace("/", "_")
    else:
        elem_id = f"{elem.attrib['class']}_{elem_w}_{elem_h}"
    if "content-desc" in elem.attrib and elem.attrib["content-desc"] and len(elem.attrib["content-desc"]) < 20:
        content_desc = elem.attrib['content-desc'].replace("/", "_").replace(" ", "").replace(":", "_")
        elem_id += f"_{content_desc}"
    return elem_id


def traverse_tree(xml_path, elem_list, attrib, add_index=False):
    path = []
    for event, elem in ET.iterparse(xml_path, ['start', 'end']):
        if event == 'end':
            path.pop()
        elif event == 'start':
            path.append(elem)
            if attrib in elem.attrib and elem.attrib[attrib] == "true":
                parent_prefix = ""
                if len(path) > 1:
                    parent_prefix = get_id_from_element(path[-2])
                bounds = elem.attrib["bounds"][1:-1].split("][")
                x1, y1 = map(int, bounds[0].split(","))
                x2, y2 = map(int, bounds[1].split(","))
                center = (x1 + x2) // 2, (y1 + y2) // 2
                elem_id = get_id_from_element(elem)
                if parent_prefix:
                    elem_id = f"{parent_prefix}_{elem_id}"
                if add_index:
                    elem_id += f"_{elem.attrib['index']}"
                close = False
                for e in elem_list:
                    bbox = e.bbox
                    center_ = (bbox[0][0] + bbox[1][0]) // 2, (bbox[0][1] + bbox[1][1]) // 2
                    dist = (abs(center[0] - center_[0]) ** 2 + abs(center[1] - center_[1]) ** 2) ** 0.5
                    if dist <= configs["MIN_DIST"]:
                        close = True
                        break
                if not close:
                    elem_list.append(AndroidElement(elem_id, ((x1, y1), (x2, y2)), attrib))


class AndroidController:
    def __init__(self, device):
        self.device = device
        self.screenshot_dir = configs["ANDROID_SCREENSHOT_DIR"]
        self.xml_dir = configs["ANDROID_XML_DIR"]
        self.width, self.height = self.get_device_size()
        self.backslash = "\\"

    def get_device_size(self):
        adb_command = f"adb -s {self.device} shell wm size"
        result = execute_adb(adb_command)
        if result != "ERROR":
            return map(int, result.split(": ")[1].split("x"))
        return 0, 0

    def get_screenshot(self, prefix, save_dir):
        cap_command = f"adb -s {self.device} shell screencap -p {os.path.join(self.screenshot_dir, f'{prefix}.png').replace(self.backslash, '/')}"
        pull_command = f"adb -s {self.device} pull {os.path.join(self.screenshot_dir, f'{prefix}.png').replace(self.backslash, '/')} {os.path.join(save_dir, f'{prefix}.png')}"
        result = execute_adb(cap_command)
        if result != "ERROR":
            result = execute_adb(pull_command)
            return os.path.join(save_dir, f"{prefix}.png") if result != "ERROR" else result
        return result

    def get_xml(self, prefix, save_dir):
        dump_command = f"adb -s {self.device} shell uiautomator dump {os.path.join(self.xml_dir, f'{prefix}.xml').replace(self.backslash, '/')}"
        pull_command = f"adb -s {self.device} pull {os.path.join(self.xml_dir, f'{prefix}.xml').replace(self.backslash, '/')} {os.path.join(save_dir, f'{prefix}.xml')}"
        result = execute_adb(dump_command)
        if result != "ERROR":
            result = execute_adb(pull_command)
            return os.path.join(save_dir, f"{prefix}.xml") if result != "ERROR" else result
        return result

    def back(self):
        adb_command = f"adb -s {self.device} shell input keyevent KEYCODE_BACK"
        return execute_adb(adb_command)

    def tap(self, tl, br):
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        adb_command = f"adb -s {self.device} shell input tap {x} {y}"
        return execute_adb(adb_command)

    def tap_point(self, x: float, y: float):
        x = int(x * self.width)
        y = int(y * self.height)
        adb_command = f"adb -s {self.device} shell input tap {x} {y}"
        return execute_adb(adb_command)

    def text(self, input_str):
        input_str = input_str.replace(" ", "%s")
        input_str = input_str.replace("'", "")
        adb_command = f"adb -s {self.device} shell input text {input_str}"
        return execute_adb(adb_command)

    def long_press(self, tl, br, duration=1000):
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        adb_command = f"adb -s {self.device} shell input swipe {x} {y} {x} {y} {duration}"
        return execute_adb(adb_command)

    def long_press_point(self, x: float, y: float, duration=1000):
        x = int(x * self.width)
        y = int(y * self.height)
        adb_command = f"adb -s {self.device} shell input swipe {x} {y} {x} {y} {duration}"
        return execute_adb(adb_command)

    def swipe(self, tl, br, direction, dist="short", quick=False):
        unit_dist = int(self.width / 10)
        if dist == "long":
            unit_dist *= 3
        elif dist == "medium":
            unit_dist *= 2
        x, y = (tl[0] + br[0]) // 2, (tl[1] + br[1]) // 2
        if direction == "down":
            offset = 0, 2 * unit_dist
        elif direction == "left":
            offset = -1 * unit_dist, 0
        elif direction == "right":
            offset = unit_dist, 0
        elif direction == "up":
            offset = 0, -2 * unit_dist
        else:
            return "ERROR"
        duration = 100 if quick else 400
        adb_command = f"adb -s {self.device} shell input swipe {x} {y} {x+offset[0]} {y+offset[1]} {duration}"
        return execute_adb(adb_command)

    def swipe_point(self, start, end, duration=400):
        start_x, start_y = int(start[0] * self.width), int(start[1] * self.height)
        end_x, end_y = int(end[0] * self.width), int(end[1] * self.height)
        adb_command = f"adb -s {self.device} shell input swipe {start_x} {start_x} {end_x} {end_y} {duration}"
        return execute_adb(adb_command)
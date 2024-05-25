
import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
import subprocess
import numpy as np
import threading
import time
import re
import datetime




selected_device = None  # 선택된 장치 ID를 저장할 글로벌 변수
selected_package_name = None  # 선택된 패키지 이름을 저장할 글로벌 변수
android_data = {}  # 각 Android 디바이스의 데이터를 저장할 딕셔너리
ios_data = {}  # 각 iOS 디바이스의 데이터를 저장할 딕셔너리
# 스레드 관리를 위한 딕셔너리
android_threads = {}
ios_threads = {}
last_valid_fps = None
# 전체 CPU 및 메모리를 저장하는 변수
cpu_cores = None
max_mem = None
is_collecting = False  # 성능 수집 중인 상태를 추적하는 변수
stop_event = threading.Event()  # 모든 스레드가 공유하는 stop_event

# 로그 파일 경로 설정
log_file_path = "performance_log.txt"

def write_to_log(message):
    """로그 파일에 메시지 기록"""
    with open(log_file_path, "a") as log_file:
        log_file.write(message + "\n")

# 전체 CPU 코어 갯수를 구하는 함수
def get_cpu_cores():
    try:
        command = "adb shell cat /proc/cpuinfo"
        output = subprocess.check_output(command, shell=True).decode('utf-8')
        cpu_cores = output.count('processor')
        return cpu_cores
    except subprocess.CalledProcessError as e:
        print("Error fetching CPU cores:", e)
        return 0


# 전체 메모리 용량을 구하는 함수
def get_max_mem():
    try:
        command = "adb shell cat /proc/meminfo"
        output = subprocess.check_output(command, shell=True).decode('utf-8')

        # 정규 표현식을 사용하여 MemTotal 값을 추출합니다.
        match = re.search(r'MemTotal:\s+(\d+)', output)
        if match:
            max_mem = int(match.group(1))  # KB 단위로 추출된 값
            return max_mem
        else:
            print("MemTotal not found in output")
            return 0
    except subprocess.CalledProcessError as e:
        print("Error fetching max memory:", e)
        return 0



##############  디바이스 연결 ####################
# 안드로이드 디바이스 정보 가져오기, adb 명령어 사용
def get_android_devices():
    result = subprocess.run(['adb', 'devices'], stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
    devices = result.stdout.partition('\n')[2].replace('\tdevice\n', '').split('\n')
    return [device for device in devices if device]

# 아이폰 디바이스 정보 가져오기 , idevice_id 명령어 사용
def get_ios_devices():
    try:
        result = subprocess.run(['idevice_id', '--list'], stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
        devices = result.stdout.strip().split('\n')
        return devices
    except FileNotFoundError:
        print("idevice_id 명령을 찾을 수 없습니다. iOS 장치 정보를 가져올 수 없습니다.")
        return []


# 연결된 기기가 안드로이드인지 아이폰인지 확인함
def get_device_model(device_id, is_android=True):
    if is_android:
        result = subprocess.run(['adb', '-s', device_id, 'shell', 'getprop', 'ro.product.model'], stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
        return result.stdout.strip()
    else:
        result = subprocess.run(['ideviceinfo', '-u', device_id, '-k', 'ProductType'], stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
        return result.stdout.strip()


# 디바이스 목록 업데이트 함수, 버튼과 연결되어 있다
def update_device_list():
    global selected_device
    global selected_package_name
    global android_data
    global ios_data
    global android_threads
    global ios_threads
    global cpu_cores, max_mem


    device_listbox.delete(0, tk.END)
    package_combobox['values'] = []
    package_combobox.set('')  # 패키지 콤보박스 선택 초기화
    android_devices = get_android_devices()
    ios_devices = get_ios_devices()

    if not android_devices and not ios_devices:
        device_listbox.insert(tk.END, "디바이스 정보 업데이트 버튼을 눌러주세요")

    # Android와 iOS 기기 목록 추가
    for device_id in android_devices + ios_devices:
        model = get_device_model(device_id, device_id in android_devices)
        device_listbox.insert(tk.END, f'{"AOS" if device_id in android_devices else "iOS"}: {model} ({device_id})')
        
        # 해당 디바이스에 대한 데이터 구조 초기화
        if device_id in android_devices:
            if device_id not in android_data:
                android_data[device_id] = {'fps': [], 'cpu': [], 'gpu': [], 'memory': [], 'temperature': []}
        elif device_id in ios_devices:
            if device_id not in ios_data:
                ios_data[device_id] = {'fps': [], 'cpu': [], 'gpu': [], 'memory': [], 'temperature': []}

    if device_listbox.size() > 0:
        device_listbox.select_set(0)
        selected_device = device_listbox.get(device_listbox.curselection()).split(' ')[-1].strip('()')
        update_package_list()

        # 선택된 디바이스의 CPU 코어 수와 최대 메모리 업데이트
        cpu_cores = get_cpu_cores()  # CPU 코어 수 업데이트
        max_mem = get_max_mem()  # 최대 메모리 업데이트

    
    
def on_package_selected(event):
    global selected_package_name
    selected_package_name = package_combobox.get()
        
        
  ##############################################
  
  
  ############### 패키지 출력 ###################
  
  # Android 기기에서 설치된 애플리케이션의 패키지 목록을 가져오는 함수
def get_installed_packages(device_id):
    cmd = ['adb', '-s', device_id, 'shell', 'pm', 'list', 'packages']
    result = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
    packages = result.stdout.splitlines()
    return [pkg.partition(':')[2] for pkg in packages]
    
  # 선택된 디바이스의 패키지 목록을 업데이트하는 함수
def update_package_list():
    # 현재 선택된 항목이 있는지 확인
    if not device_listbox.curselection():
        return
    selected_device = device_listbox.get(device_listbox.curselection())
    selected_device_id = selected_device.split(' ')[-1].strip('()')  # 디바이스 ID 추출 수정

    # 콤보박스 초기화
    package_combobox['values'] = []
    package_combobox.set('')

    if 'AOS' in selected_device:
        # Android 디바이스의 패키지 목록 가져오기
        packages = get_installed_packages(selected_device_id)
        # 'com.kakaogames'를 포함하는 패키지만 필터링
        filtered_packages = [pkg for pkg in packages if 'com.kakaogames' in pkg]
        package_names = [pkg.split(':')[-1] for pkg in filtered_packages]  # 패키지 이름만 추출
        package_combobox['values'] = package_names  # 드롭다운 목록 업데이트
        
    elif 'iOS' in selected_device:
        # iOS 디바이스 선택시 드롭다운 목록 업데이트
        package_combobox['values'] = ["설치된 패키지 목록을 불러올 수 없습니다"]


 #################################################
 
 # 현재 패키지가 실행중인지 확인하는 메서드
def is_package_running(device_id, package_name):
    try:
        result = subprocess.run(['adb', '-s', device_id, 'shell', 'pidof', package_name], stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL)
        return result.stdout.strip() != ""
    except subprocess.CalledProcessError:
        return False


# 성능 수집 시작 메서드,
def start_performance_collection():
    global is_collecting, selected_device, selected_package_name
    global android_threads, ios_threads, stop_event

    device_id = selected_device
    package_name = selected_package_name

    if not package_name:
        messagebox.showinfo("패키지 선택", "패키지를 선택해주세요")
        return

    if not is_collecting:
        if not is_package_running(device_id, package_name):
            messagebox.showinfo("앱 실행 확인", "선택된 패키지가 실행 중이 아닙니다. 성능 수집을 시작할 수 없습니다.")
            return

        if device_id in android_data:
            if device_id not in android_threads:
                stop_event.clear()
                thread = threading.Thread(target=collect_android_performance_data, args=(device_id, package_name, stop_event))
                thread.daemon = True
                thread.start()
                android_threads[device_id] = thread
        elif device_id in ios_data:
            if device_id not in ios_threads:
                stop_event.clear()
                thread = threading.Thread(target=collect_android_performance_data, args=(device_id, package_name, stop_event))
                thread.daemon = True
                thread.start()
                ios_threads[device_id] = thread
        start_collection_button.config(text="성능 수집 중단")
        is_collecting = True
    else:
        # 성능 수집 중단 로직
        stop_event.set()
        
        start_collection_button.config(text="성능 수집 시작")
        is_collecting = False

 
 ###################### 앱 시작 및 종료 기능 ##########################
 # 선택된 앱을 시작하는 함수
def start_selected_app():
    if package_combobox.get():
        package_name = package_combobox.get()
        subprocess.run(['adb', 'shell', 'monkey', '-p', package_name, '-c', 'android.intent.category.LAUNCHER', '1'], stderr=subprocess.DEVNULL)

# 선택된 앱을 종료하는 함수
def stop_selected_app():
    if package_combobox.get():
        package_name = package_combobox.get()
        subprocess.run(['adb', 'shell', 'am', 'force-stop', package_name], stderr=subprocess.DEVNULL)
        
        
####################################################################

######################## 차트 관련 부분 ###############################



################### 성능 데이터 수집 메서드 ############################


def get_window_name(package_name):
    # adb 명령어를 통해 윈도우 목록을 가져옵니다.
    cmd = "adb shell dumpsys SurfaceFlinger --list"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    # window_list = result.stdout.splitlines()

    # 패키지 이름이 포함된 윈도우 이름을 찾습니다. BLAST가 포함된 것을 우선합니다.
    for line in window_list:
        if package_name in line and "SurfaceView" in line:
            if "BLAST" in line or not any("BLAST" in l for l in window_list):
                return line
    return None
    
def get_timestamps(window_name):
    # 특수 문자 처리
    window_name_escaped = re.sub(r"([()])", r"\\\1", window_name)
    
    # adb 명령어를 통해 타임스탬프 데이터를 가져옵니다.
    cmd = f"adb shell dumpsys SurfaceFlinger --latency '{window_name_escaped}'"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    timestamps = [int(line.split()[1]) for line in result.stdout.splitlines()[1:] if line.strip()]

    return timestamps
    
def calculate_fps(timestamps):
    global last_valid_fps

    if not timestamps:
        return 0

    deltas = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
    average_frame_time_ns = sum(deltas) / len(deltas)
    fps = 1e9 / average_frame_time_ns

    # 소수점 부분 제거
    fps = round(fps)

    # 0이 아닌 경우에만 최근 유효한 FPS 값으로 저장
    if fps > 0:
        last_valid_fps = fps
        return f"FPS: {fps}"
    else:
        # 현재 FPS가 0인 경우, 이전에 저장된 값을 사용
        return f"FPS: {last_valid_fps}" if last_valid_fps is not None else "0"


# 안드로이드 GPU, 메모리, 온도 업데이트 함수
def collect_android_performance_data(device_id, package_name, stop_event):
    while not stop_event.is_set():
        fps = get_android_fps(device_id, package_name)
        cpu = get_android_cpu_usage(device_id)
        gpu = get_android_gpu_usage(device_id)
        memory = get_android_memory_usage(device_id)
        temperature = get_android_temperature(device_id)

        # 성능 데이터를 로그 파일에 기록
        log_message = f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: FPS: {fps}, CPU: {cpu}%, GPU: {gpu}%, Memory: {memory} %, Temperature: {temperature}°C"
        write_to_log(log_message)

        update_android_data_lists(device_id, fps, cpu, gpu, memory, temperature)
        time.sleep(1)


# FPS 추출 및 계산 함수
def get_android_fps(device_id, package_name):
    
    window_name = get_window_name(package_name)
    if not window_name:
        return -1
    
    timestamps = get_timestamps(window_name)
#    print(calculate_fps(timestamps))
    return calculate_fps(timestamps)

# CPU 추출 및 계산 함수
def get_android_cpu_usage(device_id):

    if cpu_cores == 0:
        print("CPU 정보를 찾을 수 없습니다.")
        return 0
    # ADB 명령어 구성
    adb_command = f"adb -s {device_id} shell top -n 1 | grep com.kakaogames.+"
    try:
        # ADB 명령어 실행
        result = subprocess.run(adb_command, shell=True, text=True, capture_output=True)
        output = result.stdout

        # CPU 사용률 추출 및 파싱
        if output:
            cpu_usage_str = output.split()[8]  # 9번째 필드(인덱스 8)가 CPU 사용률
            cpu_usage = float(cpu_usage_str.strip('%'))
            total_cpu_usage_percentage = (cpu_usage / (cpu_cores * 100)) * 100
#            print(f"CPU : {total_cpu_usage_percentage}%")
            return int(total_cpu_usage_percentage)
        else:
            return 0
    except subprocess.CalledProcessError as e:
        print(f"Error executing ADB command: {e}")
        return 0
        
# GPU 추출 및 계산 함수
def get_android_gpu_usage(device_id):
    # adb 명령어 실행
    command = f"adb -s {device_id} shell cat /sys/class/kgsl/kgsl-3d0/gpu_busy_percentage"
    try:
        output = subprocess.check_output(command, shell=True, text=True)
#        print("GPU : " + str(output.strip()) ) # GPU 사용량 문자열 반환
        return output.strip()
    except subprocess.CalledProcessError as e:
        print(f"오류 발생: {e}")
        return 0
        


# 메모리 추출 및 계산 함수
def get_android_memory_usage(device_id):
    adb_command = f"adb -s {device_id} shell top -n 1 | grep com.kakaogames.+"
    try:
        result = subprocess.run(adb_command, shell=True, text=True, capture_output=True)
        output = result.stdout

        if output:
            mem_usage_str = output.split()[5]  # 메모리 사용량 필드 추출
            mem_usage_value = float(mem_usage_str[:-1])  # 숫자 부분 추출

            # 단위에 따라 KB 단위로 변환
            if 'M' in mem_usage_str:
                mem_usage_kb = mem_usage_value * 1024  # MB -> KB
            elif 'G' in mem_usage_str:
                mem_usage_kb = mem_usage_value * 1024 * 1024  # GB -> KB
            elif 'K' in mem_usage_str:
                mem_usage_kb = mem_usage_value  # 이미 KB 단위
            else:
                mem_usage_kb = 0  # 알 수 없는 단위

            # 전체 메모리 대비 사용량 비율을 계산합니다.
            mem_usage_percentage = (mem_usage_kb / max_mem) * 100
#            print(f"Memory: {mem_usage_percentage:.2f}%")
            return int(mem_usage_percentage)
        else:
            return 0
    except subprocess.CalledProcessError as e:
        print(f"Error executing ADB command: {e}")
        return 0
        
    
    
# 온도 추출 및 계산 함수
def get_android_temperature(device_id):
    adb_command = f"adb -s {device_id} shell dumpsys battery | grep 'temperature'"
    try:
        result = subprocess.run(adb_command, shell=True, text=True, capture_output=True)
        output = result.stdout
        if output:
            temperature = output.split()[1]  # 'temperature' 라인의 2번째 필드
#            print("temperature : " + str(int(temperature) / 10.0))
            return int(temperature) / 10.0  # 배터리 온도는 1/10도 단위로 제공됨
        else:
            return 0
    except subprocess.CalledProcessError as e:
        print(f"Error executing ADB command: {e}")
        return 0

# 아이폰 GPU, 메모리, 온도 수집 로직
def collect_ios_performance_data(device_id, package_name):
    while True:
        fps = get_ios_fps(device_id)
        cpu = get_ios_cpu_usage(device_id)
        gpu = get_ios_gpu_usage(device_id)  # 추가된 로직
        memory = get_ios_memory_usage(device_id)  # 추가된 로직
        temperature = get_ios_temperature(device_id)  # 추가된 로직

        update_ios_data_lists(device_id, fps, cpu, gpu, memory, temperature)
        time.sleep(1)


# 추후 추가
def get_ios_fps(device_id):
    return 6
def get_ios_cpu_usage(device_id):
    return 7
def get_ios_gpu_usage(device_id):
    return 8
def get_ios_memory_usage(device_id):
    return 9
def get_ios_temperature(device_id):
    return 10
        
        
def update_android_data_lists(device_id, fps, cpu, gpu, memory, temperature):
    # Android 디바이스 데이터 리스트 업데이트
    global android_data  # 딕셔너리 또는 다른 구조로 관리
    android_data[device_id]['fps'].append(fps)
    android_data[device_id]['cpu'].append(cpu)
    android_data[device_id]['gpu'].append(gpu)
    android_data[device_id]['memory'].append(memory)
    android_data[device_id]['temperature'].append(temperature)
    
def update_ios_data_lists(device_id, fps, cpu, gpu, memory, temperature):
    # iOS 디바이스 데이터 리스트 업데이트
    global ios_data  # 딕셔너리 또는 다른 구조로 관리
    ios_data[device_id]['fps'].append(fps)
    ios_data[device_id]['cpu'].append(cpu)
    ios_data[device_id]['gpu'].append(gpu)
    ios_data[device_id]['memory'].append(memory)
    ios_data[device_id]['temperature'].append(temperature)
    
    

def write_to_log(message):
    """로그 파일 및 Text 위젯에 메시지 기록"""
    with open(log_file_path, "a") as log_file:
        log_file.write(message + "\n")
    log_text.insert(tk.END, message + "\n")
    log_text.see(tk.END)  # 스크롤을 가장 최근 로그로 이동



###################################################################


if __name__ == "__main__":
    # 메인 애플리케이션 윈도우
    root = tk.Tk()
    root.title("디바이스 성능 모니터링")

    # 팬으로 레이아웃 구성
    pane = ttk.Panedwindow(root, orient=tk.HORIZONTAL)
    pane.pack(fill=tk.BOTH, expand=True)

    # 디바이스 정보를 위한 왼쪽 프레임
    left_frame = ttk.Frame(pane, width=200, height=400)
    left_frame.pack_propagate(False)  # 프레임 내부 위젯이 크기를 결정하지 못하게 함
    pane.add(left_frame)
    
    
    # 로그 출력을 위한 오른쪽 프레임
    right_frame = ttk.Frame(pane, width=400, height=400)
    right_frame.pack_propagate(False)
    pane.add(right_frame)

    # 디바이스 모델 라벨과 리스트박스
    device_label = ttk.Label(left_frame, text="연결된 디바이스 모델")
    device_label.pack()
    device_listbox = tk.Listbox(left_frame)
    device_listbox.pack(fill=tk.BOTH, expand=True)
    device_listbox.insert(tk.END, "디바이스 정보 업데이트 버튼을 눌러주세요")


    # 성능 수집 시작 버튼
    start_collection_button = ttk.Button(left_frame, text="성능 수집 시작", command=start_performance_collection)
    start_collection_button.pack(fill=tk.X, pady=2)


    # 앱 시작 버튼
    start_app_button = ttk.Button(left_frame, text="앱 시작", command=start_selected_app)
    start_app_button.pack(fill=tk.X, pady=2)

    # 앱 종료 버튼
    stop_app_button = ttk.Button(left_frame, text="앱 종료", command=stop_selected_app)
    stop_app_button.pack(fill=tk.X, pady=2)

    package_combobox = ttk.Combobox(left_frame, width=50, height=12)  # height 매개변수로 드롭다운 목록의 높이 조정
    package_combobox.pack(fill=tk.BOTH, expand=True, pady=(0, 20))  # pady로 패딩 추가하여 위치 조정
    package_combobox.bind('<<ComboboxSelected>>', on_package_selected) # 사용자가 패키지를 선택했을때 발생하는 이벤트

    # 로그 출력을 위한 Text 위젯 생성 및 배치
    log_text = tk.Text(right_frame, height=400, width=400)
    log_text.pack()


    # 화면 가운데에 윈도우 위치
    root.eval('tk::PlaceWindow . center')


    # 디바이스 정보 업데이트 버튼
    update_button = ttk.Button(left_frame, text="디바이스 정보 업데이트", command=update_device_list)
    update_button.pack()


    # GUI 루프 시작
    root.mainloop()
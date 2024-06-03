import socket
import board
import busio
import time
from digitalio import DigitalInOut
from adafruit_pn532.i2c import PN532_I2C

# NFC 모듈 설정
i2c = busio.I2C(board.SCL, board.SDA)
reset_pin = DigitalInOut(board.D6)
req_pin = DigitalInOut(board.D12)
pn532 = PN532_I2C(i2c, debug=False, reset=reset_pin, req=req_pin)

# 펌웨어 버전 확인 및 MiFare 카드 설정
ic, ver, rev, support = pn532.firmware_version
print(f"Found PN532 with firmware version: {ver}.{rev}")
pn532.SAM_configuration()

def write_string_to_blocks(string, start_block):
    """ NFC 카드에 문자열을 여러 블록에 나누어 쓰는 함수 """
    for i in range(0, len(string), 4):
        block_data = string[i:i+4].ljust(4, '\0').encode()
        if not pn532.ntag2xx_write_block(start_block + i // 4, block_data):
            print(f"Failed to write to block {start_block + i // 4}")
            return False
    return True

def read_string_from_blocks(start_block, max_blocks):
    """ NFC 카드에서 문자열을 여러 블록에서 읽는 함수 """
    string = ''
    current_block = start_block
    while True:
        block_data = pn532.ntag2xx_read_block(current_block)
        if block_data is None or block_data == b'\x00\x00\x00\x00':
            break  # 데이터 끝에 도달했거나 블록 읽기 실패
        string += block_data.decode().rstrip('\0')
        current_block += 1
        if current_block - start_block >= max_blocks:
            break  # 최대 블록 수만큼 읽기
    return string

def wait_for_nfc_card():
    """ NFC 카드가 감지될 때까지 대기 """
    print("Waiting for NFC card...")
    start_time = time.time()
    while time.time() - start_time < 10:  # 10초 동안 대기
        uid = pn532.read_passive_target(timeout=0.5)
        if uid is not None:
            print("Found card with UID:", [hex(i) for i in uid])
            return True
    return False

# TCP 소켓 설정
HOST = '0.0.0.0'
PORT = 8888
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind((HOST, PORT))
server_socket.listen()

while True:
    print(f"Server is waiting for connections at {PORT}...")

    connection, client_address = server_socket.accept()
    print(f"Connected by {client_address}")
    mode = connection.recv(1024).decode().strip()

    if mode == "write":
        # 첫 번째 케이스: 플러터에서 TCP 통신으로 "write" 모드가 수신된 경우
        print("----wirte case---- Mode received: write")

        url = connection.recv(1024).decode().strip()
        print(f"----wirte case---- Received data: {url}")

        # NFC 카드가 감지될 때까지 대기
        if wait_for_nfc_card():
            if write_string_to_blocks(url, 4):
                response = "----wirte case---- URL successfully written to the NFC card."
                print("----wirte case---- URL successfully written to the NFC card.")
                
                # NFC 카드에서 문자열 읽기
                read_url = read_string_from_blocks(4, (len(url) + 3) // 4)
                print("----wirte case---- Read data from card:", read_url)
                response += f": {read_url}"
            else:
                response = "----wirte case---- Failed to write URL to the NFC card."
                print("----wirte case---- Failed to write URL to the NFC card.")
        else:
            response = "----wirte case---- No NFC card detected."
            print("----wirte case---- No NFC card detected.")

        connection.sendall(response.encode())
        print("----wirte case---- First case finished")
        connection.close()


    elif mode == "read":
        # 두 번째 케이스: 플러터에서 TCP 통신으로 "read" 모드가 수신된 경우
        print("----read case---- Mode received: read")
        
        if wait_for_nfc_card():
            # NFC 카드에서 문자열 데이터 읽기
            read_mode_url = read_string_from_blocks(4, 20)  # 예시로 최대 20개의 블록까지 읽도록 설정
            print("----read case---- Read data from card:", read_mode_url)
            connection.sendall(read_mode_url.encode())
        else:
            print("----read case---- No NFC card detected within 10 seconds.")
            connection.sendall(b"No NFC card detected within 10 seconds.")

        print("----read case---- Second case finished")
        connection.close()

    else:
        print("Invalid mode received")
        connection.sendall(b"Invalid mode")

#!/usr/bin/python3.7
# # TODO: remove traceback import traceback
# from datetime import datetime
# from email.policy import HTTP
# from operator import ne
# from optparse import OptionParser
# from pydoc import cli
# from random import getrandbits
# from sre_constants import GROUPREF_EXISTS
# import sys
# import signal
# import re
# from socket import *
# from urllib import request
# from urllib.parse import urlparse
# from _thread import import datetime
from datetime import datetime
from optparse import OptionParser
import re
import signal
import sys
from urllib.parse import urlparse
from socket import *
from _thread import *

# Signal handler for pressing ctrl-c


def ctrl_c_pressed(signal, frame):
    sys.exit(0)


BUFFER_SIZE = 65536


def is_response_200(response):
    error_code = response.split(' ')[1]
    if error_code != '200':
        return False
    else:
        return True


def validate_client_request(client_request):
    GET_INDEX = 0
    URL_INDEX = 1
    version_index = 2

    host_name_regex = '^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$'
    # Any printable ASCII characters folowed by a colon and a space then any printable ASCII characters.
    header_regex = '[ -~]+:\s[ -~]+[\\r\\n]'

    request_line = client_request[0]
    request_components = request_line.split(' ')

    validation_result = 'OK'
    try:
        URL = urlparse(request_components[URL_INDEX])
        host = URL.netloc
        path = URL.path
        scheme = URL.scheme
        hostname = URL.hostname
        port = URL.port

        if request_components[GET_INDEX] != 'GET':
            validation_result = '501 Not Implemented: only accepts get'
        elif request_components[version_index] != 'HTTP/1.0\r\n':
            validation_result = '400 Malformed Request: only accepts http/1.0'
        elif scheme != 'http':
            validation_result = '400 Malformed Request: must be http not https'
        elif not re.search(host_name_regex, hostname):
            validation_result = '400 Malformed Request: Invalid hostname'
        elif client_request[-1] != '\r\n':
            validation_result = '400 Malformed Request: no final retur'
        else:
            for header_index in range(1, len(client_request) - 1):
                header = client_request[header_index]
                if not re.search(header_regex, header):
                    validation_result = '400 Malformed Request: Invalid header'

    except Exception:
        validation_result = '400 Malformed Request: from exception'

    return validation_result


def decompose_URI_request(client_request):
    request_line = client_request[0]
    no_get_str = request_line.replace('GET', '')
    no_http_str = no_get_str.replace('HTTP/1.0', '')
    url = no_http_str.strip()
    parsed_url = urlparse(url)

    port_match = re.search(
        r':(0|[1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$', parsed_url.netloc)
    forward_slash_match = re.search(r'\/$', parsed_url.netloc)

    # Remove possible port and forward slash
    host = ''
    port_number = '80'
    if port_match:
        port_number = port_match.group()
        host = parsed_url.netloc.replace(port_number, '')
        port_number = int(port_number.replace(':', ''))
    elif forward_slash_match:
        host = parsed_url.netloc.replace(forward_slash_match, '')
        port_number = int(80)
    else:
        host = parsed_url.netloc
        port_number = int(80)

    # If there is no path, add a slash.
    path = parsed_url.path
    if path == '':
        path = '/'
    else:
        path = parsed_url.path

    request_info = (port_number, path, host)
    # print(f'r_info before: {request_info}')
    for x in range(1, len(client_request) - 1):
        if client_request[x].split(' ')[0] == 'Connection:':
            request_info = request_info + ('Connection: close',)
        else:
            request_info = request_info + (client_request[x],)
    # print(f'r_info after: {request_info}')
    return request_info


def get_server_name_and_port(client_request):
    request_info = decompose_URI_request(client_request)
    port_number = int(request_info[0])
    server_name = request_info[2]
    return (server_name, port_number)


def CONVERT_TO_GET_REQUEST(client_request):
    request_info = decompose_URI_request(client_request)
    HTTP_REQUEST = ''
    # print(f'request info: {request_info}')
    for index in range(1, len(request_info)):
        if index == 1:
            # print('in statement 1')
            HTTP_REQUEST += f'GET {request_info[index]} HTTP/1.0\r\n'
        elif index == 2:
            # print('in else statement # 2')
            HTTP_REQUEST += f'Host: {request_info[index]}\r\n'
        elif index >= 3:
            HTTP_REQUEST += f'{request_info[index]}\r\n'

    HTTP_REQUEST += '\r\n'
    return HTTP_REQUEST


def get_date():
    date = datetime.now()
    day = date.strftime('%a')
    day_of_month = date.strftime('%d')
    month = date.strftime('%b')
    year = date.strftime('%Y')
    hr = date.strftime('%H')
    min = date.strftime('%M')
    sec = date.strftime('%S')

    return f'{day}, {day_of_month} {month} {year} {hr}:{min}:{sec} GMT '


cache = {}


def client_connection_thread(client_connection_socket):
    next_request = ''
    client_request = []
    while next_request != '\r\n':
        next_request = client_connection_socket.recv(
            BUFFER_SIZE).decode()  # does this need to be encoded then decoded
        client_request.append(next_request)

    print(f'Client request: {client_request}')

    validation_result = validate_client_request(client_request)
    server_name, server_port = get_server_name_and_port(
        client_request)
    # print(f'Server: {server_name} Port: {server_port}')

    if validation_result == 'OK':
        proxy_to_server_socket = socket(AF_INET, SOCK_STREAM)
        proxy_to_server_socket.connect((server_name, server_port))

        get_request = CONVERT_TO_GET_REQUEST(client_request)

        # Check cache before connecting to server.
        decomposed_request = decompose_URI_request(client_request)
        port = decomposed_request[0]
        path = decomposed_request[1]
        host = decomposed_request[2]

        key = f'{host}:{port}{path}'

        if key in cache:

            # Conditional GET Message
            message = f'GET http://{key} HTTP/1.0\r\nHost: {host}\r\nIf-Modified-Since: {cache[key][1]}\r\n\r\n'

            proxy_to_server_socket.send(message.encode())
            server_res = proxy_to_server_socket.recv(BUFFER_SIZE).decode()

            if server_res.split(' ')[1].rstrip() == '304':
                client_connection_socket.send(cache[key][0].encode())
            elif is_response_200(server_res):
                cache[key][0] = server_res
                cache[key][1] = get_date()

                client_connection_socket.send(server_res.encode())
            else:
                client_connection_socket.send(server_res.encode())

        else:
            # print(get_request)
            proxy_to_server_socket.send(get_request.encode())
            server_response = proxy_to_server_socket.recv(
                BUFFER_SIZE).decode()  # check size
            client_connection_socket.send(server_response.encode())
            if is_response_200(server_response):
                cache[key] = [server_response, get_date()]

        proxy_to_server_socket.close()
        client_connection_socket.close()
    else:
        client_connection_socket.send(validation_result.encode())
        client_connection_socket.close()


if __name__ == '__main__':
    # Start of program execution
    # Parse out the command line server address and port number to listen to
    parser = OptionParser()
    parser.add_option('-p', type='int', dest='proxyPort')
    parser.add_option('-a', type='string', dest='proxyAddress')
    (options, args) = parser.parse_args()

    proxy_port = options.proxyPort
    proxy_address = options.proxyAddress
    if proxy_address is None:
        proxy_address = 'localhost'
    if proxy_port is None:
        proxy_port = 2100

    # Set up signal handling (ctrl-c)
    signal.signal(signal.SIGINT, ctrl_c_pressed)

    # Set up server socket
    proxy_to_client_socket = socket(AF_INET, SOCK_STREAM)
    # proxy_server_socket.bind(('', proxy_port))
    proxy_to_client_socket.bind((proxy_address, proxy_port))
    proxy_to_client_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    proxy_to_client_socket.listen(10)
    print(f'Proxy ready to accept connections.')
    # Set up client socket
    connection_count = 0
    while True:
        client_connection_socket, addr = proxy_to_client_socket.accept()
        connection_count += 1
        print(f'Connection {connection_count} established.')
        start_new_thread(client_connection_thread, (
            client_connection_socket,))

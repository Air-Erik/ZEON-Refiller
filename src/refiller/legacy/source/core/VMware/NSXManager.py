import logging
import socket
import paramiko
import time
import re


class NSXManager:
    """
    Класс для подключения к NSX Manager и получения ARP таблицы в виде словаря {mac: ip}.
    """
    def __init__(self, host, port=22, username=None, password=None, switch_name=None, timeout=2):
        """
        :param host: IP или hostname NSX Manager или Edge Node
        :param port: SSH порт (по умолчанию 22)
        :param username: имя пользователя для SSH
        :param password: пароль для SSH
        :param switch_name: имя логического переключателя (Logical Switch)
        :param timeout: время ожидания ответов CLI (в секундах)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.switch_name = switch_name
        self.timeout = timeout

        self.client = None
        self.shell = None

        self.logger = logging.getLogger(self.__class__.__name__)

    def close(self):
        if self.shell:
            try:
                self.shell.close()
            except Exception as e:
                self.logger.exception('На удалось закрыть канал %s', e)
            self.shell = None
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                self.logger.exception('На удалось закрыть клиент %s', e)
            self.client = None

    def _connect(self):
        """
        Устанавливает SSH-соединение и возвращает клиент и интерактивную оболочку.
        При повторных вызовах переиспользует уже открытое соединение.
        """
        # Если уже есть активный транспорт и открытый канал — возвращаем их
        if (
            self.client and
            self.client.get_transport() and
            self.client.get_transport().is_active() and
            self.shell and
            not getattr(self.shell, 'closed', False)
        ):
            return self.client, self.shell

        # Иначе пересоздаём соединение
        self.close()
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            self.host,
            port=self.port,
            username=self.username,
            password=self.password,
            look_for_keys=False,
            allow_agent=False,
            timeout=10
        )
        # Настраиваем keepalive, чтобы не разрывалось соединение
        client.get_transport().set_keepalive(30)

        shell = client.invoke_shell()
        # даем времени на загрузку CLI
        time.sleep(1)
        shell.recv(1000)

        self.client = client
        self.shell = shell

        return client, shell

    def reconnect(self):
        """
        Принудительно пересоздать SSH-сессию.
        """
        self.close()
        return self._connect()

    def _send_command(self, command, retry=True):
        try:
            client, shell = self._connect()
            shell.send(command + '\n')
            time.sleep(0.5)
            output = ''
            while shell.recv_ready():
                output += shell.recv(4096).decode('utf-8', errors='ignore')
            return output
        except (OSError, paramiko.SSHException, socket.error) as e:
            if retry:
                # При ошибке пробуем пересоздать соединение и повторить
                self.close()
                self.logger.exception('Ошибка отправки команды: %s', e)
                return self._send_command(command, retry=False)
            else:
                raise

    def _find_logical_switch_id(self, out):
        """
        Ищет UUID логического переключателя по его имени.
        """
        for line in out.splitlines():
            if self.switch_name and self.switch_name in line:
                parts = line.split()
                if len(parts) >= 2:
                    find_id = parts[1]
                    self.logger.info('ID: %s, Logical Switch: %s', find_id, self.switch_name)
                    return find_id
        raise ValueError('Logical Switch %s not found', self.switch_name)

    def fetch_arp_table(self):
        """
        Получает "сырую" ARP-таблицу через SSH.
        :return: строка вывода команды
        """
        # Получаем ID логического свитча
        cmd_switch = 'get logical-switch'
        out = self._send_command(cmd_switch)
        switch_id = self._find_logical_switch_id(out)

        # Получаем ARP-таблицу
        cmd_arp = f'get logical-switch {switch_id} arp-table'
        return self._send_command(cmd_arp)

    def parse_arp_table(self, raw_output):
        """
        Парсит "сырую" ARP-таблицу и возвращает словарь {mac: ip}.
        :param raw_output: текст команды ARP-таблицы
        :return: dict, где ключ — MAC-адрес, значение — IP
        """
        arp_map = {}
        for line in raw_output.splitlines():
            # ищем строки, содержащие IP и MAC
            parts = line.split()
            if len(parts) >= 4:
                ip_candidate = parts[1]
                mac_candidate = parts[2]
                if re.match(r"\d+\.\d+\.\d+\.\d+", ip_candidate) and re.match(r"[0-9A-Fa-f:]{17}", mac_candidate):
                    arp_map[mac_candidate.lower()] = ip_candidate
        return arp_map

    def get_arp_dict(self):
        """
        Всегда получает актуальную ARP-таблицу через SSH и возвращает словарь MAC->IP.
        """
        raw = self.fetch_arp_table()
        return self.parse_arp_table(raw)

    def get_ip_by_mac(self, mac_address):
        """
        Извлекает IP по MAC-адресу.
        :param mac_address: MAC-адрес в любом регистре
        :return: IP-адрес или None, если MAC отсутствует
        """
        arp = self.get_arp_dict()
        return arp.get(mac_address.lower())


if __name__ == "__main__":
    # Пример использования
    manager = NSXManager(
        host="",
        port=22,
        username="",
        password="",
        switch_name=""
    )
    # arp_dict = manager.get_arp_dict()
    # print("ARP Mapping (MAC -> IP):")
    # for mac, ip in arp_dict.items():
        # print(f"{mac} -> {ip}")

    # пример получения IP по MAC
    test_mac = "00:50:56:aa:68:16"
    print(f"IP for {test_mac}: {manager.get_ip_by_mac(test_mac)}")

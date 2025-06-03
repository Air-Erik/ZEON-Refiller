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

    def _connect(self):
        """
        Устанавливает SSH-соединение и возвращает клиент и интерактивную оболочку.
        При повторных вызовах переиспользует уже открытое соединение.
        """
        # <<< ИЗМЕНИЛ: если уже есть активное соединение — возвращаем его
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            return self.client, self.shell

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(self.host, port=self.port, username=self.username, password=self.password)
        shell = client.invoke_shell()
        # даем времени на загрузку CLI
        time.sleep(1)
        shell.recv(1000)

        self.client = client
        self.shell = shell

        return client, shell

    def _find_logical_switch_id(self, shell):
        """
        Ищет UUID логического переключателя по его имени.
        """
        shell.send("get logical-switch\n")
        time.sleep(self.timeout)
        output = shell.recv(65535).decode('utf-8')
        for line in output.splitlines():
            if self.switch_name and self.switch_name in line:
                parts = line.split()
                if len(parts) >= 2:
                    return parts[1]
        raise ValueError(f"Logical Switch '{self.switch_name}' not found")

    def fetch_arp_table(self):
        """
        Получает "сырую" ARP-таблицу через SSH.
        :return: строка вывода команды
        """
        client, shell = self._connect()

        switch_id = self._find_logical_switch_id(shell)
        cmd = f"get logical-switch {switch_id} arp-table\n"
        shell.send(cmd)
        time.sleep(self.timeout)
        output = shell.recv(65535).decode('utf-8')
        return output

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

    def close(self):
        """
        Закрывает SSH-соединение к NSX Manager.
        Вызывать при завершении работы с NSXManager.
        """
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            finally:
                self.client = None
                self.shell = None


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

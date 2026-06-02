import httpx
import re
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

from parser.settings import settings


class Parser:
    def __init__(self):
        self.headers = settings.headers
        self.client = httpx.Client(timeout=10)

    def fetch_page(self, url: str) -> str:
        try:
            response = self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"{e}")
            return None

    def parse_tariffs(self, html: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')

        result = {
            'internet': [],
            'internet_tv': [],
            'ch_internet': [],  # ch=ч типа частный)))
            'ch_internet_tv': []
        }

        collapse_block_mkd = soup.find('div', id='collapse1')

        if collapse_block_mkd:
            tables = self._find_all_tables(collapse_block_mkd)
            mkd_result = self._get_all_tables_results(tables)
            result['internet'] = mkd_result['internet']
            result['internet_tv'] = mkd_result['internet_tv']

        collapse_block_4d = soup.find('div', id='collapse2')

        if collapse_block_4d:
            tables = self._find_all_tables(collapse_block_4d)
            chd_result = self._get_all_tables_results(tables, is_private=True)

            for i, tariff in enumerate(chd_result['internet_tv']):
                if i < len(result['internet_tv']):
                    tariff['channels'] = result['internet_tv'][i]['channels']

            result['ch_internet'] = chd_result['internet']
            result['ch_internet_tv'] = chd_result['internet_tv']

        return result

    def _find_all_tables(self, block: BeautifulSoup) -> list:
        return block.find_all('table')

    def _get_all_tables_results(
        self,
        tables: list,
        is_private: bool = False
    ) -> dict:
        result = {'internet': [], "internet_tv": []}

        for table in tables:
            tariff_type = self._get_tariff_type(table)

            if tariff_type == "internet_only":
                tariffs = self._parse_internet(table, is_private)
                result['internet'].extend(tariffs)

            elif tariff_type == "internet_tv":
                tariffs = self._parse_internet_tv(table, is_private)
                result['internet_tv'].extend(tariffs)

        return result

    def _parse_internet(
        self,
        table: BeautifulSoup,
        is_private: bool = False
    ) -> list:
        tariffs = []

        for row in table.find_all('tr'):
            cells = row.find_all('td')
            if len(cells) >= 4:
                name = cells[0].get_text(strip=True)
                price = cells[1].get_text(strip=True)
                speed_kbit = cells[3].get_text(strip=True)

                if is_private:
                    name = f"{name}_ч"

                speed_mbit = self._convert_speed_to_mbit(speed_kbit)
                price_clean = self._clean_price(price)

                tariff = {
                    'name': name,
                    'channels': '',
                    'speed': speed_mbit,
                    'price': price_clean
                }
                tariffs.append(tariff)

        return tariffs

    def _parse_internet_tv(
        self,
        table: BeautifulSoup,
        is_private: bool = False
    ) -> list:
        tariffs = []

        rows = table.find_all('tr')
        if len(rows) < 2:
            return []

        header_row = rows[0]
        headers = header_row.find_all(['th', 'td'])

        internet_names = []
        for th in headers[1:]:
            name = th.get_text(strip=True)
            if name and name != 'Скорость':
                internet_names.append(name)

        speed_row_index = 1
        internet_speeds = [None] * len(internet_names)

        if len(rows) > 1:
            second_row_cells = rows[1].find_all('td')
            if second_row_cells:
                first_cell_text = second_row_cells[0].get_text()
                if 'Мбит' in first_cell_text:
                    speed_row_index = 2
                    speed_cells = rows[1].find_all('td')[1:]
                    for idx, speed_cell in enumerate(speed_cells[:len(internet_names)]): # noqa
                        speed_text = speed_cell.get_text(strip=True)
                        internet_speeds[idx] = self._get_speed_from_text(speed_text) # noqa

        for row in rows[speed_row_index:]:
            cells = row.find_all('td')
            if len(cells) < 2:
                continue

            tv_pack_name_raw = cells[0].get_text(strip=True)
            if not tv_pack_name_raw or tv_pack_name_raw == 'Скорость':
                continue

            tv_pack_name_clean = self._clean_tv_pack_name(tv_pack_name_raw)

            channels = self._get_channels_from_name(tv_pack_name_raw)

            for i, price_cell in enumerate(cells[1:len(internet_names)+1]):
                if i >= len(internet_names):
                    break

                price_text = price_cell.get_text(strip=True)
                if price_text:
                    price_clean = self._clean_price(price_text)

                    internet_name = internet_names[i]

                    speed = self._get_speed_from_text(internet_name)
                    if internet_speeds[i] and internet_speeds[i] > 0:
                        speed = internet_speeds[i]

                    if is_private:
                        tariff_name = f"{tv_pack_name_clean} + {internet_name}_ч" # noqa
                    else:
                        tariff_name = f"{tv_pack_name_clean} + {internet_name}"

                    tariff = {
                        'name': tariff_name,
                        'channels': channels if channels else '',
                        'speed': speed,
                        'price': price_clean
                    }
                    tariffs.append(tariff)

        return tariffs

    def _convert_speed_to_mbit(self, speed_text: str) -> int:
        numbers = re.findall(r'\d+', speed_text)
        if numbers:
            speed_kbit = int(numbers[0])
            return speed_kbit // 1000
        return 0

    def _get_speed_from_text(self, speed_text: str) -> int:
        numbers = re.findall(r'\d+', speed_text)
        if numbers:
            return int(numbers[0])
        return 0

    def _clean_price(self, price_text: str) -> int:
        numbers = re.findall(r'\d+', price_text)
        if numbers:
            return int(numbers[0])
        return 0

    def _get_channels_from_name(self, package_name: str) -> int:
        match = re.search(r'\((\d+)\s*канал(а|ов)?\)', package_name)
        if match:
            return int(match.group(1))
        return None

    def _clean_tv_pack_name(self, package_name: str) -> str:
        cleaned = re.sub(r'\s*\(\d+\s*канал(а|ов)?\)', '', package_name)
        return cleaned.strip()

    def _get_tariff_type(self, table: BeautifulSoup) -> str:
        prev_div = table.find_previous_sibling('div')
        if not prev_div:
            return None  # тоже ну а вдруг

        category = prev_div.get_text(strip=True)

        if 'Интернет' in category and 'ТВ' not in category:
            return 'internet_only'
        elif 'Интернет + Интерактивное ТВ' in category:
            return 'internet_tv'

        return None

    def save_xlsx(self, data: dict) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f'output/tariffs_{timestamp}.xlsx'

        all_tariffs = []

        for tariff in data['internet']:
            all_tariffs.append({
                'Название тарифа': tariff['name'],
                'Количество каналов': tariff['channels'] if tariff['channels'] else '', # noqa
                'Скорость доступа (Мбит/с)': tariff['speed'],
                'Абонентская плата (руб)': tariff['price'],
            })

        for tariff in data['internet_tv']:
            all_tariffs.append({
                'Название тарифа': tariff['name'],
                'Количество каналов': tariff['channels'] if tariff['channels'] else '', # noqa
                'Скорость доступа (Мбит/с)': tariff['speed'],
                'Абонентская плата (руб)': tariff['price'],
            })

        for tariff in data['ch_internet']:
            all_tariffs.append({
                'Название тарифа': tariff['name'],
                'Количество каналов': tariff['channels'] if tariff['channels'] else '', # noqa
                'Скорость доступа (Мбит/с)': tariff['speed'],
                'Абонентская плата (руб)': tariff['price'],
            })

        for tariff in data['ch_internet_tv']:
            all_tariffs.append({
                'Название тарифа': tariff['name'],
                'Количество каналов': tariff['channels'] if tariff['channels'] else '', # noqa
                'Скорость доступа (Мбит/с)': tariff['speed'],
                'Абонентская плата (руб)': tariff['price'],
            })

        df = pd.DataFrame(all_tariffs)

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Тарифы', index=False)

        return filepath

    def save_txt(self, data: dict) -> str:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filepath = f'output/tariffs_{timestamp}.txt'

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("=" * 60 + "\n")
            f.write("ТАРИФЫ RIALCOM\n")
            f.write("=" * 60 + "\n\n")

            f.write("ИНТЕРНЕТ (Многоквартирные дома)\n")
            f.write("=" * 60 + "\n")
            for i, tariff in enumerate(data['internet'], 1):
                f.write(f"{i}. {tariff['name']}\n")
                f.write(
                    f"   Скорость: {tariff['speed']} Мбит/с | "
                    f"Цена: {tariff['price']} руб.\n\n"
                )

            f.write("\nИНТЕРНЕТ + ТВ (Многоквартирные дома)\n")
            f.write("=" * 60 + "\n")
            for i, tariff in enumerate(data['internet_tv'], 1):
                channels = tariff['channels'] if tariff['channels'] else '—'
                f.write(f"{i}. {tariff['name']}\n")
                f.write(
                    f"   Каналов: {channels} | "
                    f"Скорость: {tariff['speed']} Мбит/с | "
                    f"Цена: {tariff['price']} руб.\n\n"
                )

            f.write("ИНТЕРНЕТ (Частные дома)\n")
            f.write("=" * 60 + "\n")
            for i, tariff in enumerate(data['ch_internet'], 1):
                f.write(f"{i}. {tariff['name']}\n")
                f.write(
                    f"   Скорость: {tariff['speed']} Мбит/с | "
                    f"Цена: {tariff['price']} руб.\n\n"
                )

            f.write("\nИНТЕРНЕТ + ТВ (Частные дома)\n")
            f.write("=" * 60 + "\n")
            for i, tariff in enumerate(data['ch_internet_tv'], 1):
                channels = tariff['channels'] if tariff['channels'] else '—'
                f.write(f"{i}. {tariff['name']}\n")
                f.write(
                    f"   Каналов: {channels} | "
                    f"Скорость: {tariff['speed']} Мбит/с | "
                    f"Цена: {tariff['price']} руб.\n\n"
                )

        return filepath

    def run(self):
        html = self.fetch_page(settings.URL)
        if not html:
            return None
        data = self.parse_tariffs(html)
        self.save_xlsx(data)
        self.save_txt(data)
        return data

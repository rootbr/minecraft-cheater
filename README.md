# MC Commander

Автоматический ввод команд Minecraft через Parallels Desktop на macOS.

## Установка

1. Убедись что установлен Rust:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

2. Собери программу:
```bash
cd mc-commander
cargo build --release
```

3. Исполняемый файл будет в `target/release/mc-commander`

## Разрешения macOS

**Важно!** Нужно дать разрешение на управление компьютером:

1. Открой **System Settings** → **Privacy & Security** → **Accessibility**
2. Нажми **+** и добавь `Terminal` (или твой терминал)
3. Если используешь из IDE — добавь её тоже

## Использование

```bash
# Базовый запуск
./target/release/mc-commander -f commands.txt

# С задержкой 500мс между командами
./target/release/mc-commander -f commands.txt -d 500

# С 10 секундами на переключение окна
./target/release/mc-commander -f commands.txt -s 10

# Пропустить первые 100 команд (если прервалось)
./target/release/mc-commander -f commands.txt -k 100
```

## Параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `-f, --file` | Путь к файлу с командами | (обязательный) |
| `-d, --delay` | Задержка между командами (мс) | 300 |
| `-s, --start-delay` | Задержка перед началом (сек) | 5 |
| `-k, --skip` | Пропустить первые N команд | 0 |

## Как использовать

1. Запусти программу в терминале
2. Быстро переключись на Parallels Desktop с Minecraft
3. Кликни в окно игры
4. Убедись что чат закрыт (Esc)
5. Программа начнёт вводить команды автоматически

## Формат файла команд

Программа автоматически:
- Пропускает пустые строки
- Пропускает строки начинающиеся с `#` (комментарии)
- Пропускает строки начинающиеся с `=` (разделители)
- Убирает `/` в начале команды (Minecraft добавит сам)

Пример файла:
```
# Это комментарий
/fill 0 64 0 10 64 10 stone
/setblock 5 65 5 torch

# Ещё команды
fill 0 65 0 10 65 10 grass_block
```

## Остановка

Нажми **Ctrl+C** в терминале чтобы остановить.

## Проблемы

**Команды не вводятся:**
- Проверь разрешения Accessibility в System Settings
- Убедись что окно Minecraft активно

**Команды вводятся слишком быстро:**
- Увеличь задержку: `-d 500` или `-d 1000`

**Прервалось на середине:**
- Посмотри номер последней команды
- Запусти с `-k <номер>` чтобы пропустить уже выполненные


## Генерация команд из GrabCraft

### Полный рабочий процесс

1. Найди постройку на [GrabCraft](https://www.grabcraft.com)
2. Скопируй URL страницы
3. Сгенерируй команды:
   ```bash
   python3 grabcraft_to_commands.py <URL> -y 70
   ```
4. Выполни команды в игре:
   ```bash
   ./target/release/mc-commander -f build_commands.mcfunction
   ```

### Быстрый старт (один скрипт)

**grabcraft_to_commands.py** - конвертирует ссылку GrabCraft напрямую в команды Minecraft Bedrock Edition.

```bash
# Простое использование - просто дай ссылку
python3 grabcraft_to_commands.py https://www.grabcraft.com/minecraft/tower/...

# С пользовательскими координатами
python3 grabcraft_to_commands.py <URL> -x 100 -y 70 -z -50

# Другой выходной файл
python3 grabcraft_to_commands.py <URL> -o my_tower.mcfunction

# Сохранить CSV блоков для анализа
python3 grabcraft_to_commands.py <URL> --save-csv blocks.csv

# Только /setblock команды (без оптимизации /fill)
python3 grabcraft_to_commands.py <URL> --no-fill
```

**Опции:**
- `-o FILE` - выходной файл (default: build_commands.mcfunction)
- `-x N` - смещение по X (default: 0)
- `-y N` - смещение по Y (default: 64 - уровень моря)
- `-z N` - смещение по Z (default: 0)
- `--no-fill` - использовать только /setblock команды
- `--save-csv [FILE]` - сохранить блоки в CSV файл

**Результат:**
- Автоматически скачивает данные с GrabCraft
- Конвертирует в правильный синтаксис Bedrock Edition
- **Умная оптимизация /fill команд:**
  - Ищет 3D кубоиды (2x2x2 и больше)
  - Ищет 2D прямоугольники (2x2 и больше)
  - Ищет 1D линии (2 блока и больше)
  - Ищет вертикальные колонны
  - **Результат: до 30% меньше команд!**
- Правильно обрабатывает лестницы, факелы, ступеньки с направлениями

**Пример оптимизации:**
- До: 479 команд (117 /fill, 362 /setblock)
- После: 336 команд (100 /fill, 236 /setblock)
- Экономия: 143 команды (-30%)

### Особенности Bedrock Edition

Скрипты автоматически конвертируют блоки в правильный синтаксис Bedrock Edition:

- **Лестницы**: `["facing_direction"=число]` вместо `[facing=направление]`
  - 2 = север, 3 = юг, 4 = запад, 5 = восток
- **Ступеньки**: `["upside_down_bit"=boolean,"weirdo_direction"=число]`
  - upside_down_bit: `false` = нормально, `true` = перевёрнуто
  - weirdo_direction: 0 = запад, 1 = восток, 2 = север, 3 = юг
  - Поддерживаются: oak_stairs, cobblestone_stairs, stone_brick_stairs
- **Факелы на стенах**: `["facing_direction"=число]`
- **Сундуки**: `["facing_direction"=число]`
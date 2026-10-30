import time

from django.core.management.base import BaseCommand, CommandError

from telegram_bot import conf, daily
from telegram_bot.api import TelegramError
from telegram_bot.handlers import handle_update


class Command(BaseCommand):
    help = "Запускает Telegram-бота (long polling). Остановка: Ctrl+C."

    def handle(self, *args, **options):
        if not conf.enabled():
            raise CommandError("Не задан TELEGRAM_BOT_TOKEN. Добавьте его в .env или переменные окружения.")

        api = conf.get_api()
        try:
            me = api.get_me()
            api.delete_webhook()   # иначе Telegram не отдаёт обновления через getUpdates
        except TelegramError as error:
            raise CommandError(f"Telegram не принял токен: {error}")

        self.stdout.write(self.style.SUCCESS(f"Бот @{me['username']} запущен. Остановка: Ctrl+C"))
        if conf.staff_chat_id() is None:
            self.stdout.write(self.style.WARNING(
                "TELEGRAM_STAFF_CHAT_ID не задан: брони и сводки в чат персонала не придут. "
                "Добавьте бота в чат и отправьте /chatid."
            ))

        offset = None
        try:
            while True:
                try:
                    if daily.due_now() and daily.run_daily(api):
                        self.stdout.write("Утренняя сводка отправлена.")
                    for update in api.get_updates(offset=offset, timeout=25):
                        offset = update['update_id'] + 1
                        try:
                            handle_update(api, update)
                        except TelegramError as error:
                            self.stderr.write(f"Ответ не отправлен: {error}")
                        except Exception as error:  # одно сломанное сообщение не должно ронять бота
                            self.stderr.write(f"Ошибка обработки обновления {update['update_id']}: {error!r}")
                except TelegramError as error:
                    self.stderr.write(f"{error}. Повтор через 5 секунд.")
                    time.sleep(5)
        except KeyboardInterrupt:
            self.stdout.write("Бот остановлен.")

from django.core.management.base import BaseCommand, CommandError

from telegram_bot import conf, daily


class Command(BaseCommand):
    help = (
        "Отправляет утреннюю сводку в чат персонала и напоминания гостям о завтрашнем заезде. "
        "runbot делает это сам в TELEGRAM_DIGEST_HOUR; команда нужна для планировщика или проверки."
    )

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help="Отправить, даже если сегодня уже отправляли")

    def handle(self, *args, force, **options):
        if not conf.enabled():
            raise CommandError("Не задан TELEGRAM_BOT_TOKEN.")
        record = daily.run_daily(conf.get_api(), force=force)
        if conf.staff_chat_id() is None:
            self.stdout.write(self.style.WARNING(
                "TELEGRAM_STAFF_CHAT_ID не задан: сводку отправлять некуда, отправлены только напоминания гостям."
            ))
        elif record is None:
            self.stdout.write("Сводка за сегодня уже отправлена. Повторить: --force")
        else:
            self.stdout.write(self.style.SUCCESS(f"Сводка отправлена, напоминаний гостям: {record.reminders}"))

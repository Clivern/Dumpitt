# MIT License
#
# Copyright (c) 2025 Clivern
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import time
import pytz
from gulper.module import Config
from gulper.module import State
from gulper.module import Logger
from gulper.core import Backup
from gulper.module import Schedule
from datetime import datetime
from gulper.module import message


class Cron:
    """
    Cron Core Functionalities
    """

    def __init__(
        self,
        config: Config,
        state: State,
        logger: Logger,
        backup: Backup,
        schedule: Schedule,
    ):
        """
        Class Constructor

        Args:
            config (Config): A config instance
            state (State): A state instance
            logger (Logger): A logger instance
            backup (Backup): A backup instance
            schedule (Schedule): A schedule instance
        """
        self._config = config
        self._state = state
        self._logger = logger
        self._backup = backup
        self._schedule = schedule

    def setup(self):
        """
        Setup calls
        """
        self._logger.get_logger().info("Connect into the state database")
        self._state.connect()
        self._logger.get_logger().info("Migrate the state database tables")
        self._state.migrate()

    def run(self, is_daemon: bool):
        """
        Run Cron Jobs

        Args:
            is_daemon (bool): whether to run it as a daemon
        """
        if is_daemon:
            message("Cron daemon started..")

        while True:
            dbs = self._config.get_databases()

            for db, configs in dbs.items():
                schedule_name = configs.get("schedule", None)

                if not schedule_name:
                    continue

                schedule = self._config.get_schedule_config(schedule_name)

                if not schedule:
                    self._logger.get_logger().error(
                        f"Unable to find schedule {schedule_name}"
                    )
                    continue

                prev_cron_run = self._schedule.get_cron_prev_run(
                    schedule.get("expression")
                )
                next_cron_run = self._schedule.get_cron_next_run(
                    schedule.get("expression")
                )
                current_utc = self._schedule.get_current_utc()

                if current_utc >= prev_cron_run and current_utc < next_cron_run:
                    backup = self._state.get_latest_backup(db)

                    if backup:
                        # Validate that the backup was in the past or not
                        created_at = datetime.strptime(
                            backup.get("createdAt"), "%Y-%m-%d %H:%M:%S"
                        )
                        created_at_utc = created_at.replace(tzinfo=pytz.UTC)
                        if (
                            created_at_utc >= prev_cron_run
                            and created_at_utc < next_cron_run
                        ):
                            # The backup was not in the past, don't run another backup
                            self._logger.get_logger().info(
                                f"Database with name {db} had a backup at {created_at} so skip cron"
                            )
                            continue

                    # Run a new backup
                    self._backup.run(db)

            if not is_daemon:
                break
            else:
                time.sleep(60)


def get_cron(
    config: Config, state: State, logger: Logger, backup: Backup, schedule: Schedule
) -> Cron:
    """
    Get Cron Class Instance

    Args:
        config (Config): A config instance
        state (State): A state instance
        logger (Logger): A logger instance
        backup (Backup): A backup instance
        schedule (Schedule): A schedule instance

    Returns:
        Cron: An instance of cron class
    """
    return Cron(config, state, logger, backup, schedule)

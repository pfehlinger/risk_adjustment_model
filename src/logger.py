import logging
import logging.config
import os
import glob
from datetime import datetime

def initialize_logger(log_path=None):
    """
    Configures the logger
    """
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'class': 'logging.Formatter',
                'format': "%(asctime)s %(levelname)-8s %(name)-50s %(message)s",
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
            },
            'file': {
                'class': 'logging.FileHandler',
                'formatter': 'standard',
                'filename': log_path,
                'mode': 'w',
            },
        },
        'loggers': {
            'risk_adjustment_scoring': {
                'level': 'DEBUG',
                'handlers': ['console', 'file'],
            }
        }
    }

    if log_path is None:
        del config['handlers']['file']
        del config['loggers']['risk_adjustment_scoring']['handlers'][1]

    logging.config.dictConfig(config)


def clear_old_logs(path, days=1, **args):
    keep_key_word = args.get('keep_key_word')
    log = args.get('log')
    log_files = glob.glob(f'{str(path)}{os.sep}*.log')

    keep = []
    for log in log_files:
        # Keep files from past days were days is the input parameter
        name = log.split(os.sep)[-1]
        ts = name.split('_')[-1]
        log_ymd = ts[0:8]

        today = datetime.today().strftime('%Y%m%d')
        delta = datetime.strptime(today, '%Y%m%d') - datetime.strptime(log_ymd, '%Y%m%d')
        # if delta.days < days:
        #     keep.append(log)
        # else:
        #     with open(log) as f:
        #         f = f.readlines()

        #     for line in f:
        #         if (keep_key_word is not None) and (keep_key_word in line) and (delta.days < 30):
        #             keep.append(log)
        #             break

    for log in log_files:
        if log not in keep:
            os.remove(log)

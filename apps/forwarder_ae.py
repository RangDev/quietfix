"""Compatibility alias. Prefer backup_ae.py; all runtime backup requests use MN/Mcc."""
from backup_ae import step, main

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass

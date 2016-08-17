def run_app():
    from xtrade.app import run_app
    run_app()


def test():
    from subprocess import call
    call(['py.test', '-v', '-s'])


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 2 and sys.argv[1] == 'test':
        test()
    else:
        run_app()

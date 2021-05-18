from eventloop import EventLoop, FileSystemWatch, Timer, SingleShotTimer, walk
from colorama import Fore, Back, Style, init as colorama_init
import os
import shutil
import datetime

def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class Logger:

    def __init__(self, src, dst, short):
        self._src = src
        self._dst = dst
        self._short = short

    def print_info(self, msg):
        print(Fore.WHITE + now_str() + " " + Fore.YELLOW + Style.BRIGHT + msg + Fore.RESET + Style.NORMAL)

    def print_error(self, msg):
        print(Fore.WHITE + now_str() + " " + Fore.RED + msg + Fore.RESET)

    def print_copied(self, src, dst):
        if self._short:
            print(Fore.WHITE + now_str() + " " + Fore.GREEN + Style.BRIGHT + os.path.relpath(dst, self._dst) + Fore.RESET + Style.NORMAL)
        else:
            print(Fore.WHITE + now_str() + " " + Fore.GREEN + Style.BRIGHT + src + Fore.WHITE + ' -> ' + Fore.GREEN + dst + Fore.RESET + Style.NORMAL)

def makedirs(path):
    try:
        os.makedirs(path)
    except OSError:
        pass

def create_dir(src, dst, logger):
    dst_dir = os.path.dirname(dst)
    makedirs(dst_dir)
    ok = os.path.isdir(dst_dir)
    if not ok:
        logger.print_error("Failed to create {}".format(dst_dir))
    return ok

def remove_dst(src, dst, logger):
    if not os.path.exists(dst):
        return True
    try:
        os.remove(dst)
    except Exception as e:
        logger.print_error("Failed to remove {}".format(dst))
        logger.print_error(e)
        return False
    return True

def copy_to_dst(src, dst, logger):
    try:
        shutil.copy(src, dst)
    except Exception as e:
        logger.print_error("Failed to copy {} -> {}".format(src, dst))
        logger.print_error(e)
        return False
    return True

class Schedule:
    def __init__(self, logger):
        self._timer = None
        self._tasks = []
        self._logger = logger
        
    def append(self, src, dst, timeout, deduplicate = True):
        if isinstance(src, list):
            srcs = src
            dsts = dst
        else:
            srcs = [src]
            dsts = [dst]
        for (src, dst) in zip(srcs, dsts):
            add = True
            if deduplicate:
                for (src_, dst_) in self._tasks:
                    if src_ == src:
                        add = False
            if add:
                self._tasks.append((src, dst))
        self._schedule(timeout)

    def _schedule(self, timeout):
        timer = self._timer
        if timer:
            timer.stop()
        timer = SingleShotTimer()
        timer.start(timeout, self.onTimer)
        self._timer = timer

    def onTimer(self):
        self._timer = None

        logger = self._logger

        tasks = []

        for (src, dst) in self._tasks:
            if not os.path.isfile(src):
                continue
            ok = create_dir(src, dst, logger)
            ok = ok and remove_dst(src, dst, logger)
            ok = ok and copy_to_dst(src, dst, logger)
            if not ok:
                logger.print_info("Rescheduling {}".format(src))
                tasks.append((src, dst))
            else:
                logger.print_copied(src, dst)

        self._tasks = tasks
        if len(tasks) > 0: # if any task failed to complete, reschedule them
            self._schedule(10)

def main():
    import argparse

    colorama_init()

    example_text = """examples:
    mugi-sync /path/to/src /path/to/dst -i "*.cpp" -e "moc_*" ".git"
    mugi-sync /src/path/libfoo.dll /dst/path
    mugi-sync /path/to/src /path/to/dst --no-initial-sync
    """

    parser = argparse.ArgumentParser(prog="mugi-sync", epilog=example_text, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('src', help="Source directory or file")
    parser.add_argument('dst', help="Destination directory or file")
    parser.add_argument('--include','-i', nargs='+', help="Include globs")
    parser.add_argument('--exclude','-e', nargs='+', help="Exclude globs")
    parser.add_argument('--no-initial-sync', action='store_true', help="Disable initial sync")
    parser.add_argument('--create', action='store_true', help="Create target directory")
    parser.add_argument('--short-log', action='store_true', help="Short log")
    args = parser.parse_args()

    #print(args); exit(0)

    logger = Logger(args.src, args.dst, args.short_log)

    if args.create:
        makedirs(args.dst)
        if not os.path.isdir(args.dst):
            logger.print_error("Failed to create {}".format(args.dst))
            return



    if os.path.isdir(args.src) and os.path.isfile(args.dst):
        logger.print_error("{} is dir and {} is file, cannot syncronize dir to file".format(args.src, args.dst))
        parser.print_help()
        return

    schedule = Schedule(logger)

    def dst_path(path):
        dst = None
        if os.path.isfile(args.src):
            if os.path.isfile(args.dst):
                dst = args.dst
            elif os.path.isdir(args.dst):
                dst = os.path.join(args.dst, os.path.basename(args.src))
            else:
                logger.print_error("{} not a file not a dir".format(args.dst))
                return
        elif os.path.isdir(args.src):
            if os.path.isfile(args.dst):
                pass
            elif os.path.isdir(args.dst):
                dst = os.path.join(args.dst, os.path.relpath(path, args.src))
            else:
                logger.print_error("{} not a file not a dir".format(args.dst))
                return
        else:
            logger.print_error("{} not a file not a dir".format(args.src))
            return
        return dst

    def onChange(path, event):
        src = path
        dst = dst_path(src)
        schedule.append(src, dst, 1)

    def initial_sync():
        dirs, files = walk(args.src, args.include, args.exclude)
        srcs = []
        dsts = []
        for src in files:
            dst = dst_path(src)
            if not os.path.exists(dst):
                add = True
            else:
                m1 = os.path.getmtime(src)
                m2 = os.path.getmtime(dst)
                add = m2 <= m1
            if add:
                srcs.append(src)
                dsts.append(dst)
        if len(srcs) > 0:
            schedule.append(srcs, dsts, 1, deduplicate=False)
            
    loop = EventLoop()

    if not args.no_initial_sync:
        logger.print_info("Initial sync")
        initial_sync()

    watch = FileSystemWatch()
    logger.print_info("Watching {}".format(args.src))
    watch.start(args.src, onChange, recursive=True, include=args.include, exclude=args.exclude)
    loop.start()

if __name__ == "__main__":
    main()
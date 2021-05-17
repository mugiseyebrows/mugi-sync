from eventloop import EventLoop, FileSystemWatch, Timer, SingleShotTimer, walk
import os
import shutil

def makedirs(path):
    try:
        os.makedirs(path)
    except OSError:
        pass

def create_dir(src, dst):
    dst_dir = os.path.dirname(dst)
    makedirs(dst_dir)
    ok = os.path.isdir(dst_dir)
    if not ok:
        print("Failed to create {}".format(dst_dir))
    return ok

def remove_dst(src, dst):
    if not os.path.exists(dst):
        return True
    try:
        os.remove(dst)
    except Exception as e:
        print("Failed to remove {}".format(dst))
        print(e)
        return False
    return True

def copy_to_dst(src, dst):
    try:
        shutil.copy(src, dst)
    except Exception as e:
        print("Failed to copy {} -> {}".format(src, dst))
        print(e)
        return False
    return True

class Schedule:
    def __init__(self):
        self._timer = None
        self._tasks = []

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

        tasks = []

        for (src, dst) in self._tasks:
            if not os.path.isfile(src):
                continue
            ok = create_dir(src, dst)
            ok = ok and remove_dst(src, dst)
            ok = ok and copy_to_dst(src, dst)
            if not ok:
                print("Rescheduling {} -> {}".format(src, dst))
                tasks.append((src, dst))
            else:
                print("Copied {} -> {}".format(src, dst))

        self._tasks = tasks
        if len(tasks) > 0: # if any task failed to complete, reschedule them
            self._schedule(10)

def main():
    import argparse    
    
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
    args = parser.parse_args()

    #print(args); exit(0)

    if args.create:
        makedirs(args.dst)
        if not os.path.isdir(args.dst):
            print("Failed to create {}".format(args.dst))
            return

    if os.path.isdir(args.src) and os.path.isfile(args.dst):
        print("{} is dir and {} is file, cannot syncronize dir to file".format(args.src, args.dst))
        parser.print_help()
        return

    schedule = Schedule()

    def dst_path(path):
        dst = None
        if os.path.isfile(args.src):
            if os.path.isfile(args.dst):
                dst = args.dst
            elif os.path.isdir(args.dst):
                dst = os.path.join(args.dst, os.path.basename(args.src))
            else:
                print("{} not a file not a dir".format(args.dst))
                return
        elif os.path.isdir(args.src):
            if os.path.isfile(args.dst):
                pass
            elif os.path.isdir(args.dst):
                dst = os.path.join(args.dst, os.path.relpath(path, args.src))
            else:
                print("{} not a file not a dir".format(args.dst))
                return
        else:
            print("{} not a file not a dir".format(args.src))
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
        initial_sync()

    watch = FileSystemWatch()
    watch.start(args.src, onChange, recursive=True, include=args.include, exclude=args.exclude)
    loop.start()

if __name__ == "__main__":
    main()
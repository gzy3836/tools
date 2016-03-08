#!/usr/bin/env python
#coding=utf-8
'''
暂无断点续传功能
'''

import time
import threading
import urllib2
import sys
import os
import multiprocessing

#创建最大线程数
max_thread = 4

#创建锁
lock = threading.RLock()


class Downloader(threading.Thread):
    #初始化线程的一些参数
    def __init__(self, url, start_size, end_size, f_obj, buffer):
        self.url = url
        self.buffer = buffer
        self.start_size = start_size
        self.end_size = end_size
        self.f_obj = f_obj
        threading.Thread.__init__(self)


    def run(self):
        self._download()

    def _download(self):
        '''添加Range是为了创建headers中的Content-Range属性，
        就能读取指定的start-->end部分了，使每个线程取自己的那一部分size
        '''
        req = urllib2.Request(self.url)
        req.headers['Range'] = 'bytes=%s-%s' % (self.start_size, self.end_size)

        #创建个socket文件句柄
        f = urllib2.urlopen(req)

        #偏移量设置到开头处
        offset = self.start_size

        #开始读取指定范围内的数据，并写入文件
        while 1:
            block = f.read(self.buffer)

            if not block:
                break

            #开始写数据，使用with语法，自动加锁/释放锁
            with lock:
                #第一次写入前，游标seek到设置好的偏移量处，然后开始写
                self.f_obj.seek(offset)
                self.f_obj.write(block)
                #写完后，偏移量移到刚写入的数据块的最后
                offset = offset + len(block)



def progress(url, save_file, width=50):
    '''
这是个进度条，原理就是每隔1秒获取一下写入文件的大小，然后和源文件进行对比,
获得一个整数作为此时百分比，这里有个坑：就是获取当前文件大小的时候不要用os.path.getsize()
因为用这个到的是不是文件的真实大小----空洞文件
比如说这个程序我用的是4个线程来工作，每个线程分得1/4，那么最后的线程的start-offset会
被定位到最后一个数据范围的起始处，也就是3/4处，75%，所以刚开始进度就会是75%...
所以找到了这个方法：os.stat(file).st_blocks * 512
'''
    req = urllib2.urlopen(url)
    size = float(req.info()['Content-Length'])
    while 1:
        real_size = os.stat(save_file).st_blocks * 512
        percent = int(real_size / size * 100)
        sys.stdout.write( "\r[%s] %d%%" % (('%%-%ds' % width) % (width * percent / 100 * '='), percent))
        sys.stdout.flush()
        time.sleep(1)
        if percent == 100:
            print
            break


def main(url, thread=3, save_file='', buffer=4096):
    #如果设置的线程数大于默认最大值，则取max_thread
    thread = thread if thread <= max_thread else max_thread

    req = urllib2.urlopen(url)
    size = int(req.info().getheaders('Content-Length')[0])

    fobj = open(save_file, 'wb')

    #---------------------------------------------------------
    #根据线程数平均分配下载文件的总量
    avg_size, pad_size = divmod(size, thread)

    plist = []

    #分配每个线程的start-end偏移量
    for i in xrange(thread):
        start_size = i * avg_size
        end_size = start_size + avg_size - 1
        if i == thread - 1:
            end_size = end_size + pad_size + 1

        #创建线程并添加进列表
        t = Downloader(url, start_size,end_size, fobj, buffer)
        plist.append(t)

    #那个进度条我又单独开了个进程，也可以用线程
    p = multiprocessing.Process(target=progress,args=(url, save_file,))

    #-----------------------------------------------
    print '开始下载... %s ...' % save_file
    p.start()

    for t in plist:
        t.start()

    for t in plist:
        t.join()

    fobj.close()
    p.join()
    print "下载完成"



if __name__ == '__main__':
    url = 'http://dldir1.qq.com/qqfile/qq/QQ7.7/16096/QQ7.7.exe'
    save_file = os.path.basename(url)
    try:
        print '10秒后开始下载.请确定网络良好.因为没有断点续传功能.呵呵\n停止请按Ctrl+c'
        time.sleep(10)
        main(url=url, thread=10, save_file=save_file)
    except (KeyboardInterrupt, SystemExit):
        print '\nbye'
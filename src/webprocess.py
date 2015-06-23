# coding=utf-8

import datetime
import time
import os
import queue
import html
from zipfile import ZipFile, is_zipfile
import shutil
import base64
from enum import IntEnum

try:
    import winsound
except:
    has_winsound = False
else:
    has_winsound = True

# ---------------------

from flask import (Flask, render_template, request,
                  make_response, redirect, 
                  send_from_directory)

from werkzeug import secure_filename

# ---------------------

import wvars
from db_wrapper import *
from datadefine import *
from rpi_stat import *

web = Flask(__name__, 
            static_folder=wvars.static_folder, 
            template_folder=wvars.template_folder)

web_back_queue = None
back_web_queue = None

gcfg = None
db = None

template_cache = dict()
login_manager = c_login_manager()

class PG_TYPE(IntEnum):
    GATHER = 0
    CATEGORY = 1
    SOURCE = 2
    M_GATHER = 3
    M_CATEGORY = 4
    P_GATHER = 5
    P_CATEGORY = 6
    P2_GATHER = 7
    P2_CATEGORY = 8

class DV_TYPE(IntEnum):
    COMPUTER = 0
    PAD = 1
    MOBILE = 2

wrong_key_html = ('在当前的用户配置中，没有找到相应版块。<br>'
                  '请刷新整个页面，以更新左侧的版块目录。')

zero_user_loaded = ('尚未载入任何用户，请在3秒后刷新此页面。<br>'
                   '如问题依旧，请检查用户配置、后端进程的状态。'
                   )

jump_to_login = r'<script>top.location.href="/login";</script>'

#-------------------------------
#         page part
#-------------------------------

# page nag part
def generate_page(all_count, now_pg, 
                  col_per_page, 
                  p_type, category):

    def make_pattern(p_type, category):
        # computer
        if p_type == PG_TYPE.GATHER:
            template_tuple = ('<a href="/list', str(category), 
                              '/%d" target="_self">%s</a>')
        elif p_type == PG_TYPE.CATEGORY:
            template_tuple = ('<a href="/list/', category,
                              '/%d" target="_self">%s</a>')
        elif p_type == PG_TYPE.SOURCE:
            template_tuple = ('<a href="/slist/', category,
                              '/%d" target="_self">%s</a>')
        # mobile
        elif p_type == PG_TYPE.M_GATHER:
            template_tuple = ('<a href="/ml', str(category), 
                              '/%d" target="_self">%s</a>')
        elif p_type == PG_TYPE.M_CATEGORY:
            template_tuple = ('<a href="/ml/', category,
                              '/%d" target="_self">%s</a>')
        # pad
        elif p_type == PG_TYPE.P2_GATHER:
            template_tuple = ('<a href="/pad', str(category), 
                              '/%d#bd" target="_self">%s</a>')
        elif p_type == PG_TYPE.P2_CATEGORY:
            template_tuple = ('<a href="/pad/', category,
                              '/%d#bd" target="_self">%s</a>')

        elif p_type == PG_TYPE.P_GATHER:
            template_tuple = ('<a href="/plist', str(category), 
                              '/%d" target="_self">%s</a>')
        elif p_type == PG_TYPE.P_CATEGORY:
            template_tuple = ('<a href="/plist/', category,
                              '/%d" target="_self">%s</a>')

        return ''.join(template_tuple)


    last_pg = (all_count // col_per_page) + \
              (1 if (all_count % col_per_page) else 0)

    if now_pg < 1:
        now_pg = 1
    elif now_pg > last_pg:
        now_pg = last_pg

    # numbers width
    if p_type in (PG_TYPE.M_GATHER, PG_TYPE.M_CATEGORY):
        sides = 3
    else:
        sides = 5
    begin_pg = now_pg - sides
    end_pg = now_pg + sides

    if begin_pg < 1:
        end_pg += 1 - begin_pg

    if end_pg > last_pg:
        begin_pg -= end_pg - last_pg
        end_pg = last_pg

    if begin_pg < 1:
        begin_pg = 1

    # format template
    template = template_cache.get((p_type, category))
    if template == None:
        template = make_pattern(p_type, category)
        template_cache[(p_type, category)] = template

    # mobile
    if p_type in (PG_TYPE.M_GATHER, PG_TYPE.M_CATEGORY):
        
        # nag
        lst1 = list()
        # 首页
        if now_pg > 1:
            s = template % (1, '首页')
            lst1.append(s)
        else:
            lst1.append('首页')

        # 末页
        if now_pg < last_pg:
            s = template % (last_pg, '末页&nbsp;&nbsp;&nbsp;')
            lst1.append(s)
        else:
            lst1.append('末页&nbsp;&nbsp;&nbsp;')

        # 上页
        if now_pg > 1:
            s = template % (now_pg-1, '上页')
            lst1.append(s)
        else:
            lst1.append('上页')

        # 下页
        if now_pg < last_pg:
            s = template % (now_pg+1, '下页')
            lst1.append(s)  
        else:
            lst1.append('下页')

        # numbers
        lst2 = list()
        lst2.append('共%d页' % last_pg)
        for i in range(begin_pg, end_pg+1):
            if i == now_pg:
                ts = '<strong>%d</strong>' % i
            else:
                ts = template % (i, str(i))
            lst2.append(ts)

        return '&nbsp;&nbsp;'.join(lst2) + \
               '<br>' + \
               '&nbsp;&nbsp;'.join(lst1)

    # pc & pad
    else:
        lst = list()

        lst.append('共%d页' % last_pg)

        # 首页
        if now_pg > 1:
            s = template % (1, '首页')
            lst.append(s)
        else:
            lst.append('已到')

        # 末页
        if now_pg < last_pg:
            s = template % (last_pg, '末页')
            lst.append(s)
        else:
            lst.append('已到')

        # numbers
        for i in range(begin_pg, end_pg+1):
            if i == now_pg:
                ts = '<strong>%d</strong>' % i
            else:
                ts = template % (i, str(i))
            lst.append(ts)

        # 上页
        if now_pg > 1:
            s = template % (now_pg-1, '上页')
            lst.append(s)
        else:
            lst.append('已到')

        # 下页
        if now_pg < last_pg:
            s = template % (now_pg+1, '下页')
            lst.append(s)  
        else:
            lst.append('已到')

        return '&nbsp;'.join(lst)

#-------------------------------
#           generate_list
#-------------------------------
# generate list
def generate_list(username, category, pagenum, p_type, sid=''):
    if pagenum < 1:
        pagenum = 1

    # limit and offset
    if p_type in (PG_TYPE.M_GATHER, PG_TYPE.M_CATEGORY):
        limit = 10
    else:
        limit = db.get_colperpage_by_user(username)
    offset = limit * (pagenum-1)

    # content list
    if p_type == PG_TYPE.SOURCE:
        all_count = db.get_count_by_sid(sid)
        if all_count == -1:
            return None, None, None, None, None
        
        lst = db.get_infos_by_sid(username, sid, offset, limit)
        if lst == None:
            return None, None, None, None, None
    else:
        all_count = db.get_count_by_user_cate(username, category)
        if all_count == -1:
            return None, None, None, None, None
        
        lst = db.get_infos_by_user_category(username, category, 
                                            offset, limit)

    # nag part
    page_html = generate_page(all_count, pagenum,
                              limit, 
                              p_type, category)

    # current time
    int_now_time = int(time.time())

    # 时:分:秒
    now_time = datetime.datetime.\
               fromtimestamp(int_now_time).\
               strftime('%H:%M:%S')

    recent_8h = int_now_time - 3600*8
    recent_24h = int_now_time - 3600*24

    for i in lst:
        if i.fetch_date > recent_8h:
            i.temp = 1
        elif i.fetch_date > recent_24h:
            i.temp = 2
        
        # 月-日 时:分
        i.fetch_date = datetime.datetime.\
                       fromtimestamp(i.fetch_date).\
                       strftime('%m-%d %H:%M')

    if p_type in (PG_TYPE.GATHER, PG_TYPE.M_GATHER,
                  PG_TYPE.P2_GATHER, PG_TYPE.P_GATHER):
        if category == 0:
            category = '普通、关注、重要'
        elif category == 1:
            category = '关注、重要'
        elif category == 2:
            category = '重要'
    elif p_type == PG_TYPE.SOURCE:
        category = db.get_name_by_sid(sid)
        
    return lst, all_count, page_html, now_time, category

# return username or None
def check_cookie():
    ha = request.cookies.get('user')
    if ha:
        # return username or None
        return db.get_user_from_hash(ha)
    else:
        return None

@web.route('/')
def index():
    if not check_cookie():
        return jump_to_login

    return render_template('main.html')

@web.route('/login', methods=['GET', 'POST'])
def login():
    # check hacker
    ip = request.remote_addr
    allow, message = login_manager.login_check(ip)
    if not allow:
        return message

    # load 0 user
    if db.get_user_number() == 0:
        return render_template('login.html', msg=zero_user_loaded)

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        ha = db.login(username, password)

        if ha:
            subname = request.form.get('name')
            if subname == 'toc':
                target = '/'
            elif subname == 'top':
                target = '/pad0'
            else:
                target = '/m'
            response = make_response(redirect(target))

            # 失效期2038年
            response.set_cookie('user', 
                                value=ha, 
                                expires=2147483640)
            return response
        else:
            login_manager.login_fall(ip)
            return render_template('login.html',
                                    msg='无此用户或密码错误')

    return render_template('login.html')

user_type_str = ('公共帐号', '普通帐号', '管理员')
def general_index(page_type):
    username = check_cookie()
    if not username:
        return jump_to_login
    
    # user type
    usertype = db.get_usertype(username)
    allow = True if usertype > 0 else False

    if request.method == 'POST':
        name = request.form.get('name')

        # logout
        if name == 'logout':
            html = jump_to_login
            response = make_response(html)
            response.set_cookie('user', expires=0)
            return response

        # fetch my sources
        elif usertype > 0 and name == 'fetch_mine':
            lst = db.get_fetch_list_by_user(username)
            c_message.make(web_back_queue, 'wb:request_fetch', 0, lst)

    # category list
    category_list = db.get_category_list_by_username(username)
    
    # render template
    if page_type == DV_TYPE.COMPUTER:
        page = 'left.html'
    elif page_type == DV_TYPE.PAD:
        page = 'p.html'
    else:
        page = 'm.html'
    
    return render_template(page, 
                           usertype=user_type_str[usertype],
                           username=username,
                           allowfetch=allow,
                           categories=category_list)

@web.route('/left', methods=['GET', 'POST'])
def left():
    return general_index(DV_TYPE.COMPUTER)

@web.route('/m', methods=['GET', 'POST'])
def mobile():
    return general_index(DV_TYPE.MOBILE)
    
@web.route('/p', methods=['GET', 'POST'])
def pad():
    return general_index(DV_TYPE.PAD)

# 各页面通用的列表生成
def general_list(category, pagenum, p_type, sid=''):   
    username = check_cookie()
    if not username:
        return jump_to_login
    
    t1 = time.perf_counter()

    lst, all_count, page_html, now_time, category = \
            generate_list(username, category, 
                          pagenum, p_type, sid)
    
    if lst == None:
        return wrong_key_html
    
    if p_type in (PG_TYPE.M_GATHER, PG_TYPE.M_CATEGORY):
        page = 'mlist.html'
    elif p_type in (PG_TYPE.P_GATHER, PG_TYPE.P_CATEGORY):
        page = 'plist.html'
    else:
        page = 'list.html'
        
    t2 = time.perf_counter()
    during = '%.5f' % (t2-t1)

    return render_template(page, 
                           entries=lst, listname=category, 
                           count=all_count, htmlpage=page_html,
                           nowtime=now_time, time=during)  

@web.route('/ml/<category>')
@web.route('/ml/<category>/<int:pagenum>')
def mobile_list(category, pagenum=1):   
    return general_list(category, pagenum, PG_TYPE.M_CATEGORY)

@web.route('/ml<int:level>')
@web.route('/ml<int:level>/<int:pagenum>')
def mobile_default(level, pagenum=1):
    return general_list(level, pagenum, PG_TYPE.M_GATHER)

@web.route('/list/<category>')
@web.route('/list/<category>/<int:pagenum>')
def computer_list(category, pagenum=1):
    return general_list(category, pagenum, PG_TYPE.CATEGORY)

@web.route('/list<int:level>')
@web.route('/list<int:level>/<int:pagenum>')
def computer_default(level, pagenum=1):
    return general_list(level, pagenum, PG_TYPE.GATHER)

@web.route('/plist/<category>')
@web.route('/plist/<category>/<int:pagenum>')
def pad_list(category, pagenum=1):
    return general_list(category, pagenum, PG_TYPE.P_CATEGORY)

@web.route('/plist<int:level>')
@web.route('/plist<int:level>/<int:pagenum>')
def pad_default(level, pagenum=1):
    return general_list(level, pagenum, PG_TYPE.P_GATHER)

@web.route('/slist/<encoded_url>')
@web.route('/slist/<encoded_url>/<int:pagenum>')
def slist(encoded_url='', pagenum = 1):
    try:
        sid = base64.urlsafe_b64decode(encoded_url).decode('utf-8')
    except:
        return '请求的信息源列表url有误:<br>' + encoded_url

    return general_list(encoded_url, pagenum,
                        PG_TYPE.SOURCE, sid)
    
def general_pad2(category, pagenum, p_type):
    username = check_cookie()
    if not username:
        return jump_to_login

    t1 = time.perf_counter()
    
    # 横竖屏，默认竖屏
    orientation = request.cookies.get('orientation')
    landscape = True if orientation == 'landscape' else False

    # user type
    usertype = db.get_usertype(username)
    allow = True if usertype > 0 else False

    if request.method == 'POST':
        name = request.form.get('name')

        # logout
        if name == 'logout':
            html = jump_to_login
            response = make_response(html)
            response.set_cookie('user', expires=0)
            return response
        
        # 横竖屏，默认竖屏
        elif name == 'switch':
            response = make_response(redirect('/pad0'))
            v = 'portrait' if orientation == 'landscape' else 'landscape'
            response.set_cookie('orientation', 
                                value=v, 
                                expires=2147483640)
            return response

        # fetch my sources
        elif usertype > 0 and name == 'fetch_mine':
            lst = db.get_fetch_list_by_user(username)
            c_message.make(web_back_queue, 'wb:request_fetch', 0, lst)

    # category list
    category_list = db.get_category_list_by_username(username)
    
    # list  
    lst, all_count, page_html, now_time, category = \
            generate_list(username, category, 
                          pagenum, p_type)
    
    if lst == None:
        return wrong_key_html
        
    t2 = time.perf_counter()
    during = '%.5f' % (t2-t1)

    return render_template('pad.html',
                           landscape=landscape,
                           usertype=user_type_str[usertype],
                           username=username,
                           allowfetch=allow,
                           categories=category_list,
                           entries=lst, listname=category,
                           count=all_count, htmlpage=page_html,
                           nowtime=now_time, time=during
                           )

@web.route('/pad<int:level>', methods=['GET', 'POST'])
@web.route('/pad<int:level>/<int:pagenum>', methods=['GET', 'POST'])
def pad2_default(level, pagenum=1):
    return general_pad2(level, pagenum, PG_TYPE.P2_GATHER)
    
@web.route('/pad/<category>', methods=['GET', 'POST'])
@web.route('/pad/<category>/<int:pagenum>', methods=['GET', 'POST'])
def pad2_list(category, pagenum=1):
    return general_pad2(category, pagenum, PG_TYPE.P2_CATEGORY)

@web.route('/cateinfo')
def cate_info():
    username = check_cookie()
    if not username:
        return jump_to_login

    show_list = db.get_forshow_by_user(username)
    all_s_num, set_s_num = db.get_sourcenum_by_user(username)

    return render_template('cateinfo.html', show_list=show_list,
                            cate_num=len(show_list),
                            allnum=all_s_num, setnum=set_s_num)

def zip_cfg():
    # del .zip files in temp directory first
    files = os.listdir(wvars.upload_forlder)
    for f in files:
        fpath = os.path.join(wvars.upload_forlder, f)
        if not os.path.isdir(fpath) and f.endswith('.zip'):
            try:
                os.remove(fpath)
            except:
                pass

    # target file-name
    int_now_time = int(time.time())
    date_str = datetime.datetime.\
               fromtimestamp(int_now_time).\
               strftime('%y%m%d_%H%M')
    dst = 'cfg' + date_str
    dst = os.path.join(wvars.upload_forlder, dst)


    root_path = gcfg.root_path
    newfile = shutil.make_archive(dst, 'zip', root_path, 'cfg')

    return wvars.upload_forlder, os.path.split(newfile)[1]

def prepare_db_for_download():
    # del .db files in temp directory first
    files = os.listdir(wvars.upload_forlder)
    for f in files:
        fpath = os.path.join(wvars.upload_forlder, f)
        if not os.path.isdir(fpath) and f.endswith('.db'):
            try:
                os.remove(fpath)
            except:
                pass

    # current db
    db.compact_db()
    db_file, db_size = db.get_current_file()

    # target file-name
    int_now_time = int(time.time())
    date_str = datetime.datetime.\
               fromtimestamp(int_now_time).\
               strftime('%y%m%d_%H%M%S')
    dst = 'sql' + date_str + '.db'
    dst = os.path.join(wvars.upload_forlder, dst)

    # copy from database directory
    newfile = shutil.copy2(db_file, dst)

    return wvars.upload_forlder, os.path.split(newfile)[1]

@web.route('/panel', methods=['GET', 'POST'])
def panel():
    username = check_cookie()
    if not username:
        return jump_to_login

    usertype = db.get_usertype(username)
    
    if usertype == 2 and request.method == 'POST':
        if 'name' in request.form:
            name = request.form['name']

            # download cfg.zip
            if name == 'download_cfg':
                fpath, fname = zip_cfg()
                return send_from_directory(directory=fpath, 
                                           filename=fname,
                                           as_attachment=True)
            # 压缩数据库
            elif name == 'compact_db':
                print('try to compact database file')
                db.compact_db()

            # 下载数据库
            elif name == 'download_db':
                fpath, fname = prepare_db_for_download()
                return send_from_directory(directory=fpath, 
                                           filename=fname,
                                           as_attachment=True)

            # download weberr.txt
            elif name == 'download_err':
                fpath = os.path.join(wvars.upload_forlder, 'weberr.txt')
                if os.path.isfile(fpath):
                    return send_from_directory(
                           directory=wvars.upload_forlder, 
                           filename='weberr.txt',
                           as_attachment=True)

            # 更新所有
            elif name == 'fetch_all':
                c_message.make(web_back_queue, 'wb:request_fetch')

            # 删除所有异常
            elif name == 'del_except':
                print('try to delete all exceptions')
                db.del_all_exceptions()

            elif name == 'backup_db':
                db.compact_db()
                db.backup_db()

            elif name == 'reload_data':
                c_message.make(web_back_queue, 'wb:request_load')
                
            elif name == 'maintain_db':
                db.db_process()

        elif 'file' in request.files:
            f = request.files['file']
            if f and f.filename and f.filename.lower().endswith('.zip'):
                # save to file
                fpath = os.path.join(wvars.upload_forlder, 'uploaded.zip')
                f.save(fpath)

                if not is_zipfile(fpath):
                    return '无效zip文件'

                cfg_path = os.path.join(gcfg.root_path, 'cfg')
                zftmp = os.path.join(wvars.upload_forlder,'tmp')

                # remove & make tmp dir
                try:
                    shutil.rmtree(zftmp)
                except Exception as e:
                    print('删除/temp/tmp时出现异常，这可能是正常现象。')

                try:
                    os.mkdir(zftmp)
                except Exception as e:
                    print('创建/temp/tmp时出现异常。', e)

                # extract to tmp dir
                try:
                    zf = ZipFile(fpath)
                    namelist = zf.namelist()
                    zf.extractall(zftmp)
                    zf.close()
                except Exception as e:
                    return '解压错误' + str(e)

                # copy to cfg dir
                if 'config.ini' in namelist:
                    cp_src_path = zftmp
                elif 'cfg/config.ini' in namelist:
                    cp_src_path = os.path.join(zftmp, 'cfg')
                else:
                    return 'zip文件里没有找到config.ini文件'

                try:
                    shutil.rmtree(cfg_path)
                except Exception as e:
                    return '无法删除cfg目录' + str(e)

                try:
                    shutil.copytree(cp_src_path, cfg_path)
                except Exception as e:
                    return '无法复制cfg目录' + str(e)

                print('.zip has been extracted')
                c_message.make(web_back_queue, 'wb:request_load')

    db_file, db_size = db.get_current_file()
    info_lst = get_info_list(gcfg, usertype, db_file, db_size)
    proc_lst = get_python_process(gcfg)

    # exception infos
    if usertype == 2:
        exceptions = db.get_all_exceptions()
    else:
        exceptions = db.get_exceptions_by_username(username)
        
    for i in exceptions:
        i.fetch_date = datetime.datetime.\
                       fromtimestamp(i.fetch_date).\
                       strftime('%m-%d %H:%M')
    
    return render_template('panel.html', type = usertype,
                           info_list=info_lst, proc_list=proc_lst,
                           entries = exceptions)


@web.route('/listall')
def listall():
    username = check_cookie()
    if not username:
        return jump_to_login

    usertype = db.get_usertype(username)
    if usertype != 2:
        return '请使用管理员帐号查看此页面'
    
    listall = db.get_listall()
    return render_template('listall.html', items=listall,
                           user_num=db.get_user_number(),
                           source_num=len(listall)
                           )

@web.errorhandler(404)
def page_not_found(e):
    s = ('无效网址<br>'
         '<a href="/" target="_top">点击此处返回首页</a>'
         )
    return s

def write_weberr(exception):
    # del weberr.txt if size > 1M
    fpath = os.path.join(wvars.upload_forlder, 'weberr.txt')
    try:
        size = os.path.getsize(fpath)
    except:
        size = -1
        
    if size > 1024 * 1024:
        try:
            os.remove(fpath)
        except:
            pass

    # write to weberr.txt
    with open(fpath, 'a') as f:
        f.write(time.ctime() + '\n' + \
                str(type(exception)) + ' ' + \
                str(exception) + '\n\n')

    # print to console
    print('web-side exception:', str(exception))

@web.errorhandler(500)
def internal_error(exception):
    # beep
    if has_winsound:
        winsound.Beep(600, 1000)
        
    write_weberr(exception)
    return str(exception)

@web.route('/check')
def check_bw_queue():
    if request.remote_addr != '127.0.0.1':
        print('%s请求检查web端队列，忽略' % request.remote_addr)
        return ''

    print('/check')

    while True:
        try:
            msg = back_web_queue.get(block=False)
        except queue.Empty:
            break
        
        if msg.token == wvars.cfg_token:
            if msg.command == 'bw:send_infos':
                db.add_infos(msg.data)
    
            elif msg.command == 'bw:source_finished':
                db.source_finished(msg.data)
    
            elif msg.command == 'bw:db_process_time':
                db.db_process()
                login_manager.maintenace()
                
            elif msg.command == 'bw:source_timeout':
                for sid, stime, ttime in msg.data:
                    start = str(datetime.datetime.fromtimestamp(stime))
                    s = '%s超时，始于%s，超时限制%d秒' % (sid,start,ttime)
                    write_weberr(s)

        elif msg.command == 'bw:send_config_users':
                # token
                wvars.cfg_token = msg.data[0]

                # config
                cfg = msg.data[1]
                cfg.web_pid = os.getpid()
                print('pid(web, back):', cfg.web_pid, cfg.back_pid)

                global gcfg
                gcfg = cfg

                template_cache.clear()
                login_manager.clear()

                # users
                users = msg.data[2]
                print('web-side got users: %d' % len(users))
                db.add_users(cfg, users)
                
        else:
            print('web can not handle:', msg.command, msg.token)

    return ''

def run_web(web_port, certfile, keyfile, tmpfs_path,
            wb_queue, bw_queue):

    # queues
    global web_back_queue
    web_back_queue = wb_queue

    global back_web_queue
    back_web_queue = bw_queue

    # database
    global db
    db = c_db_wrapper(tmpfs_path)

    c_message.make(web_back_queue, 'wb:request_load')

    # tornado
    from tornado.wsgi import WSGIContainer
    from tornado.httpserver import HTTPServer
    from tornado.ioloop import IOLoop

    try:
        if certfile:
            import ssl
            context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            
            cf = os.path.join(wvars.root_path, certfile)
            if keyfile:
                kf = os.path.join(wvars.root_path, keyfile)
            else:
                kf = None
            
            context.load_cert_chain(certfile=cf, keyfile=kf)
        else:
            context = None
        
        http_server = HTTPServer(WSGIContainer(web), ssl_options=context)
        http_server.listen(web_port)
        IOLoop.instance().start()
    except Exception as e:
        print('启动web服务器时出现异常，异常信息:')
        print(e)

    #-----------------
    # web service
    #-----------------
    #web.run(host='0.0.0.0', port=web_port)#, debug=True) 

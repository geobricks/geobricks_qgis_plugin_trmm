from ftplib import FTP
from server.geobricks_trmm.config.trmm_config import config as conf


def list_years(username, password):
    """
    List all the available years.
    @return: An array of code/label objects.
    """
    if conf['source']['type'] == 'FTP':
        ftp = FTP(conf['source']['ftp']['base_url'])
        ftp.login(username, password)
        ftp.cwd(conf['source']['ftp']['data_dir'])
        l = ftp.nlst()
        ftp.quit()
        l.sort(reverse=True)
        out = []
        for s in l:
            try:
                int(s)
                out.append({'code': s, 'label': s})
            except ValueError:
                pass
        return out

def list_months(username, password, year):
    """
    List all the available months.
    @param year: e.g. '2010'
    @type year: str | int
    @return: An array of code/label objects.
    """
    if conf['source']['type'] == 'FTP':
        ftp = FTP(conf['source']['ftp']['base_url'])
        ftp.login(username, password)
        ftp.cwd(conf['source']['ftp']['data_dir'])
        ftp.cwd(str(year))
        l = ftp.nlst()
        ftp.quit()
        l.sort()
        out = []
        for s in l:
            out.append({'code': s, 'label': s})
        return out


def list_days(username, password, year, month):
    """
    List all the available days.
    @param year: e.g. '2010'
    @type year: str | int
    @param month: e.g. '02'
    @type month: str | int
    @return: An array of code/label objects.
    """
    month = month if type(month) is str else str(month)
    month = month if len(month) == 2 else '0' + month
    if conf['source']['type'] == 'FTP':
        ftp = FTP(conf['source']['ftp']['base_url'])
        ftp.login(username, password)
        ftp.cwd(conf['source']['ftp']['data_dir'])
        ftp.cwd(str(year))
        ftp.cwd(month)
        l = ftp.nlst()
        ftp.quit()
        l.sort()
        out = []
        for s in l:
            out.append({'code': s, 'label': s})
        return out


def list_layers(username, password, year, month, day):
    """
    List all the available layers for a given year and month.
    @param year: e.g. '2010'
    @type year: str | int
    @param month: e.g. '02'
    @type month: str | int
    @param day: e.g. '02'
    @type day: str | int
    @return: An array of code/label/extensions objects.
    """
    month = month if type(month) is str else str(month)
    month = month if len(month) == 2 else '0' + month
    day = day if type(day) is str else str(day)
    day = day if len(day) == 2 else '0' + day
    if conf['source']['type'] == 'FTP':
        ftp = FTP(conf['source']['ftp']['base_url'])
        ftp.login(username, password)
        ftp.cwd(conf['source']['ftp']['data_dir'])
        ftp.cwd(str(year))
        ftp.cwd(month)
        ftp.cwd(day)
        l = ftp.nlst()
        ftp.quit()
        l.sort()
        fao_layers = filter(lambda x: '.tif' in x, l)
        out = []
        for layer in fao_layers:
            if '.7.' in layer or '.7A.' in layer:
                code = layer
                hour = layer[0:layer.index('.tif')].split('.')[2]
                label = layer[0:layer.index('.tif')].split('.')[0]
                label += ' ('
                label += '-'.join([str(year), month, day])
                label += ', ' + hour + ')'
                out.append({'code': code, 'label': label, 'extensions': ['.tif', '.tfw']})
        return out


def list_layers_subset(username, password, year, month, from_day, to_day):
    """
    List all the available layers for a given year and month.
    @param year: e.g. '2010'
    @type year: str | int
    @param month: e.g. '02'
    @type month: str | int
    @from_day: e.g. 01
    @type from_day: str | int
    @to_day: e.g. 05
    @type to_day: str | int
    @return: An array of code/label/extensions objects.
    """
    year = str(year)
    month = month if type(month) is str else str(month)
    month = month if len(month) == 2 else '0' + month
    from_day = from_day if type(from_day) is str else str(from_day)
    from_day = from_day if len(from_day) == 2 else '0' + from_day
    to_day = to_day if type(to_day) is str else str(to_day)
    to_day = from_day if len(to_day) == 2 else '0' + to_day
    file_path_root = 'ftp://' + conf['source']['ftp']['base_url'] + conf['source']['ftp']['data_dir']
    days = map(lambda x: str(x) if x > 9 else '0'+str(x), range(int(from_day), 1+int(to_day)))
    out = []
    if conf['source']['type'] == 'FTP':
        ftp = FTP(conf['source']['ftp']['base_url'])
        ftp.login(username, password)
        ftp.cwd(conf['source']['ftp']['data_dir'])
        ftp.cwd(year)
        ftp.cwd(month)
        for i in range(0, len(days)):
            if i > 0:
                ftp.cwd('../')
            ftp.cwd(days[i])
            l = ftp.nlst()
            l.sort()
            fao_layers = filter(lambda x: '.tif' in x, l)
            for layer in fao_layers:
                if '.7.' in layer or '.7A.' in layer:
                    code = layer
                    hour = layer[0:layer.index('.tif')].split('.')[2]
                    label = layer[0:layer.index('.tif')].split('.')[0]
                    label += ' ('
                    label += '-'.join([year, month, days[i]])
                    label += ', ' + hour + ')'
                    file_path = file_path_root + year + '/' + month + '/' + days[i] + '/' + code
                    out.append({
                        'file_name': code,
                        'file_path': file_path,
                        'label': label,
                        'size': None
                    })
                    code = code.replace('.tif', '.tfw')
                    file_path = file_path_root + year + '/' + month + '/' + days[i] + '/' + code
                    out.append({
                        'file_name': code,
                        'file_path': file_path,
                        'label': label,
                        'size': None
                    })
        ftp.quit()
        return out


def list_layers_month_subset(username, password, year, month):
    """
    List all the available layers for a given year and month.
    @param year: e.g. '2010'
    @type year: str | int
    @param month: e.g. '02'
    @type month: str | int
    @return: An array of code/label/extensions objects.
    """
    year = str(year)
    month = month if type(month) is str else str(month)
    month = month if len(month) == 2 else '0' + month
    file_path_root = 'ftp://' + conf['source']['ftp']['base_url'] + conf['source']['ftp']['data_dir']
    out = []
    if conf['source']['type'] == 'FTP':
        ftp = FTP(conf['source']['ftp']['base_url'])
        ftp.login(username, password)
        ftp.cwd(conf['source']['ftp']['data_dir'])
        ftp.cwd(year)
        ftp.cwd(month)
        days = ftp.nlst()
        days.sort()
        for i in range(0, len(days)):
            if i > 0:
                ftp.cwd('../')
            ftp.cwd(days[i])
            l = ftp.nlst()
            l.sort()
            fao_layers = filter(lambda x: '.tif' in x, l)
            for layer in fao_layers:
                if '.7.' in layer or '.7A.' in layer:
                    code = layer
                    hour = layer[0:layer.index('.tif')].split('.')[2]
                    label = layer[0:layer.index('.tif')].split('.')[0]
                    label += ' ('
                    label += '-'.join([year, month, days[i]])
                    label += ', ' + hour + ')'
                    file_path = file_path_root + year + '/' + month + '/' + days[i] + '/' + code
                    out.append({
                        'file_name': code,
                        'file_path': file_path,
                        'label': label,
                        'size': None
                    })
                    code = code.replace('.tif', '.tfw')
                    file_path = file_path_root + year + '/' + month + '/' + days[i] + '/' + code
                    out.append({
                        'file_name': code,
                        'file_path': file_path,
                        'label': label,
                        'size': None
                    })
        ftp.quit()
        return out

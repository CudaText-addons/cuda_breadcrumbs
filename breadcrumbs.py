import os
from pathlib import Path
from collections import namedtuple
from itertools import zip_longest

from cudatext import *


"""
#TODO
* update icons
* handle hidden CodeTree
"""

dir_settings = app_path(APP_DIR_SETTINGS)
fn_config    = os.path.join(dir_settings, 'plugins.ini')
OPT_SEC      = 'breadcrumbs'

opt_root_dir_source = [0]
opt_show_root_parents = True
opt_file_sort_type = 'name'

PROJECT_DIR = None

SHOW_CODE = False

#CodeItem = namedtuple('CodeItem', 'name icon')

h_tree      = app_proc(PROC_GET_CODETREE, "")
h_im_tree   = tree_proc(h_tree, TREE_GET_IMAGELIST)


def bool_to_str(v): return '1' if v else '0'
def str_to_bool(s): return s=='1'

def get_carets_tree_path():
    if not SHOW_CODE:
        return ()

    def get_caret_node(carets, parent=0): #SKIP
        items = tree_proc(h_tree, TREE_ITEM_ENUM, id_item=parent)
        if items:
            for id_,name in items:
                #print(f'.. checking name:{name}')

                x0,y0, x1,y1 = tree_proc(h_tree, TREE_ITEM_GET_RANGE, id_item=id_)
                if x0 == -1:
                    child_id = get_caret_node(carets, id_)
                    if child_id is not None:
                        #print(f'NOTE: returning -1')
                        return child_id
                    continue

                if all((y0,x0) <= (c[1],c[0]) <= (y1,x1)  and  (c[2] == -1 or (y0,x0) <= (c[3],c[2]) <= (y1,x1))
                                for c in carets):
                    child_id = get_caret_node(carets, id_)
                    return child_id  if child_id is not None else  id_

                child_id = get_caret_node(carets, id_)
                if child_id is not None:
                    return child_id

    carets = ed.get_carets()
    if carets:
        node_id = get_caret_node(carets)

        if node_id:
            #print(f'target tyree node: {(node_id,)}')
            names = []
            id_ = node_id
            while True:
                props = tree_proc(h_tree, TREE_ITEM_GET_PROPS, id_item=id_)
                names.append(props['text'] or '<empty>')

                if not props  or  props['parent'] == 0:
                    break

                id_ = props['parent']

            names.reverse()
            return names
    return ()

def get_project_dir():
    """ choose project root directory: .opt_root_dir_source
    """
    import cuda_project_man

    path = None
    for optval in opt_root_dir_source:
        if optval == 0: # project file dir
            path = cuda_project_man.project_variables()["ProjDir"]
        elif optval == 1: # first node
            _nodes = cuda_project_man.global_project_info.get('nodes')
            path = _nodes[0] if _nodes else None
        elif optval == 2: # project's main-file dir
            path = cuda_project_man.global_project_info.get('mainfile')
            if path:
                path = os.path.dirname(path)

        if path:
            return path


class Command:

    def __init__(self):
        self._load_config()

        self._ed_uis = {} # h_ed -> Bread
        self.is_loading_sesh = False

        Colors.update()

    def _load_config(self):
        global PROJECT_DIR
        global opt_root_dir_source
        global opt_show_root_parents
        global opt_file_sort_type

        PROJECT_DIR = get_project_dir()

        _root_dir_source_val = ini_read(fn_config, OPT_SEC, 'root_dir_source', '0')
        try:
            opt_root_dir_source = list(map(int, _root_dir_source_val.split(',') ))
        except:
            print('NOTE: Breadcrumbs - Unable to parse option value: "root_dir_source" should be '
                    + 'comma-separated string of integers 0-2')

        opt_show_root_parents = str_to_bool(ini_read(fn_config, OPT_SEC, 'show_root_parents', '1'))
        opt_file_sort_type = ini_read(fn_config, OPT_SEC, 'file_sort_type', opt_file_sort_type)


    def config(self):
        _root_dir_source_str = ','.join(map(str, opt_root_dir_source))
        ini_write(fn_config, OPT_SEC, 'root_dir_source',   _root_dir_source_str)
        ini_write(fn_config, OPT_SEC, 'show_root_parents', bool_to_str(opt_show_root_parents) )
        ini_write(fn_config, OPT_SEC, 'file_sort_type', opt_file_sort_type)
        file_open(fn_config)

    #def on_caret(self, ed_self):
        #self._update(ed_self)

    def on_open(self, ed_self):
        if not self.is_loading_sesh:
            self._update(ed_self)

    def on_save(self, ed_self):
        self._update(ed_self)

    def on_focus(self, ed_self):
        if ed_self.get_prop(PROP_HANDLE_SELF) not in self._ed_uis:
            self._update(ed_self)


    def on_state(self, ed_self, state):
        # tree changed
        if state == APPSTATE_THEME_UI:
            Colors.update()
            for bread in self._ed_uis.values():
                bread.on_theme()

        # session loading start
        elif state == APPSTATE_SESSION_LOAD_BEGIN: # started
            self.is_loading_sesh = True
        elif state in [APPSTATE_SESSION_LOAD_FAIL, APPSTATE_SESSION_LOAD]: # ended
            self.is_loading_sesh = False

            visible_eds = (ed_group(i)  for i in range(9))
            for edt in filter(None, visible_eds):
                self.on_open(edt)

        elif state == APPSTATE_PROJECT:
            global PROJECT_DIR

            new_project_dir = get_project_dir()
            if PROJECT_DIR != new_project_dir:
                PROJECT_DIR = new_project_dir
                for bread in self._ed_uis.values():
                    bread.update()

        #elif state == APPSTATE_CODETREE_AFTER_FILL:
            #self._update(ed)

    def on_cell_click(self, id_dlg, id_ctl, data='', info=''):
        # info: "<cell_ind>:<h_ed>"
        cell_ind, h_ed = map(int, info.split(':'))
        bread = self._ed_uis[h_ed]
        bread.on_click(cell_ind)


    def _update(self, ed_self):
        h_ed = ed_self.get_prop(PROP_HANDLE_SELF)

        bc = self._ed_uis.get(h_ed)
        if bc is None:
            bc = Bread(ed_self)
            self._ed_uis[h_ed] = bc

        bc.update()

    @property
    def current(self):
        return self._ed_uis.get(ed.get_prop(PROP_HANDLE_SELF))


class Bread:
    def __init__(self, ed_self):
        self.ed = Editor(ed_self.get_prop(PROP_HANDLE_SELF))  if ed_self is ed else  ed_self

        self._tree = None
        self._root = None
        self._path_items = []
        self._code_items = []

        self._add_ui()
        self.reset()
        self.on_theme()


    @property
    def fn(self):
        return self.ed.get_filename()  or  self.ed.get_prop(PROP_TAB_TITLE)

    @property
    def tree(self):
        if self._tree is None:

            from .dlg import TreeDlg

            self._tree = TreeDlg(opts={'sort_type':opt_file_sort_type})
        return self._tree

    def _add_ui(self):
        self.hparent = self.ed.get_prop(PROP_HANDLE_PARENT)
        self.n_sb    = dlg_proc(self.hparent, DLG_CTL_ADD, 'statusbar')
        self.h_sb    = dlg_proc(self.hparent, DLG_CTL_HANDLE, index=self.n_sb)
        dlg_proc(self.hparent, DLG_CTL_PROP_SET, index=self.n_sb, prop={
            'color': Colors.bg,
            #'align': ALIGN_TOP,
        })
        try:
            statusbar_proc(self.h_sb, STATUSBAR_SET_PADDING, value=2) # api=399
        except NameError:
            pass



    def reset(self):
        self._path_items.clear()
        self._code_items.clear()
        statusbar_proc(self.h_sb, STATUSBAR_DELETE_ALL)

    def update(self):
        root_changed = self._root != PROJECT_DIR
        self._root = PROJECT_DIR
        if not opt_show_root_parents  and  self._root  and  self.fn.startswith(self._root):
            root = Path(self._root)
            path_items = Path(self.fn).relative_to(root.parent).parts
        else:
            path_items = Path(self.fn).parts

        code_items = get_carets_tree_path()

        # no changes
        if not root_changed  and  self._path_items == path_items  and  self._code_items == code_items:
            return

        if root_changed \
                or len(self._path_items) != len(path_items) \
                or len(self._code_items) != len(code_items):
            if opt_show_root_parents  and  self._root  and  self.fn.startswith(self._root):
                _n_prefix = len(Path(self._root).parent.parts)
            else:
                _n_prefix = 0
            self._update_bgs(len(path_items),  len(code_items),  _n_prefix)

        # update changed  PATH  cells
        for i,(old,new) in enumerate(zip_longest(self._path_items, path_items)):
            if old != new  and  new is not None:
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i, value=new)
                _h_ed = self.ed.get_prop(PROP_HANDLE_SELF)
                _callback = "module={};cmd={};info={}:{};".format(
                                        'cuda_breadcrumbs', 'on_cell_click', i, _h_ed)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_CALLBACK, index=i, value=_callback)
        # update changed  CODE  cells
        offset = len(path_items)
        for i,(old,new) in enumerate(zip_longest(self._code_items, code_items)):
            if old != new  and  new is not None:
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i+offset, value=str(new))
                '!!!'
                # update icons from tree data
                #statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_TEXT, index=i, value=new)

        self._path_items = path_items
        self._code_items = code_items


    def on_click(self, cell_ind):
        if len(self._path_items) == 1: # no file
            return

        # if path-item click
        if cell_ind < len(self._path_items):
            path = Path(*self._path_items[:cell_ind+1])
            if self._root  and  not opt_show_root_parents: # add root if is hidden
                path = Path(self._root).parent / path
            btn_rect = self._get_cell_rect(cell_ind)
            _parent = path.parent.as_posix()  if path.parent else  path.as_posix()
            self.tree.show_dir(fn=path.as_posix(), root=_parent, btn_rect=btn_rect)

        else:   # if code-item click
            code_ind = cell_ind - len(self._path_items)
            print(f'code clicked: {Path(*self._path_items)} -- {self._code_items[:code_ind+1]}')


    def on_theme(self):
        dlg_proc(self.hparent, DLG_CTL_PROP_SET, index=self.n_sb, prop={ 'color': Colors.bg })

        n_path = len(self._path_items)
        for i in range(n_path): # path cell colors
            set_cell_colors(self.h_sb, i, bg=Colors.path_bg, fg=Colors.path_fg)

        _code_inds = range(n_path, n_path+len(self._code_items))
        for i in _code_inds:    # code cell colors
            set_cell_colors(self.h_sb, i, bg=Colors.path_bg, fg=Colors.path_fg)

        statusbar_proc(self.h_sb, STATUSBAR_SET_COLOR_BORDER_R, value=Colors.border)
        statusbar_proc(self.h_sb, STATUSBAR_SET_COLOR_BORDER_TOP, value=Colors.border)


    def _update_bgs(self, n_path, n_code, n_prefix):
        _old_n_path = len(self._path_items)  if self._path_items else  0
        _old_n_code = len(self._code_items)  if self._code_items else  0
        old_n_total = _old_n_path + _old_n_code

        new_n_total = n_path + n_code

        # fix cell count
        if new_n_total  >  old_n_total:     # too few
            for i in range(new_n_total - old_n_total):
                ind = statusbar_proc(self.h_sb, STATUSBAR_ADD_CELL)
                statusbar_proc(self.h_sb, STATUSBAR_SET_CELL_AUTOSIZE, index=ind, value=True)

        elif new_n_total  <  old_n_total:   # too many
            for i in range(old_n_total - new_n_total):
                statusbar_proc(self.h_sb, STATUSBAR_DELETE_CELL, index=new_n_total)

        for i in range(n_path): # update path cells bg+fg
            _bg = Colors.path_bg  if not opt_show_root_parents or i >= n_prefix else  Colors.path_bg_root_parents
            set_cell_colors(self.h_sb, i, bg=_bg, fg=Colors.path_fg)

        for i in range(n_path, n_path+n_code): # update code cells bg+fg
            set_cell_colors(self.h_sb, i, bg=Colors.code_bg, fg=Colors.code_fg)


    def _get_cell_rect(self, ind):
        """ returns screen coords: x,y, w,h
        """
        get_cell_size = lambda i: statusbar_proc(self.h_sb, STATUSBAR_GET_CELL_SIZE, index=i)

        p = dlg_proc(self.hparent, DLG_CTL_PROP_GET, index=self.n_sb)
        x,y, w,h = p['x'],p['y'], p['w'], p['h'] # local statusbar coords
        sb_screen_coords = dlg_proc(self.hparent, DLG_COORD_LOCAL_TO_SCREEN, index=x, index2=y)

        cell_w = get_cell_size(ind)
        cell_sizes = (get_cell_size(i)  for i in range(ind))
        cell_x = sum(cell_sizes)
        return (
            sb_screen_coords[0]+cell_x, # x
            sb_screen_coords[1],        # y
            cell_w,  # w
            h,       # h
        )




class Colors:
    @classmethod
    def update(cls):
        colors = app_proc(PROC_THEME_UI_DICT_GET, '')

        cls.bg      = colors['EdTextBg'     ]['color']

        cls.path_bg = colors['TabBg'        ]['color']
        cls.path_fg = colors['TabFont'      ]['color']
        cls.path_bg_root_parents = colors['SideBg']['color']

        cls.code_bg = colors['TabActive'    ]['color']
        cls.code_fg = colors['TabFontActive']['color']

        cls.border = colors['TabBorderActive']['color']


def set_cell_colors(h_sb, ind, bg, fg):
    statusbar_proc(h_sb, STATUSBAR_SET_CELL_COLOR_BACK, index=ind, value=bg)
    statusbar_proc(h_sb, STATUSBAR_SET_CELL_COLOR_FONT, index=ind, value=fg)

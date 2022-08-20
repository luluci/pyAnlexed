from typing import List, Callable
import re
import pathlib


class gram:
    class cond_log_type:
        def __init__(self, file_path: pathlib.Path, line_no: int, line: str, match: re.Match, name: str) -> None:
            self.file_path: pathlib.Path = file_path
            self.line_no: int = line_no
            self.line: str = line
            self.match: re.Match = match
            self.name = name

    class cond_log_list:
        def __init__(self, len: int, parent=None) -> None:
            parent: gram.cond_log_list

            self.parent: gram.cond_log_list = parent
            self.log = [gram.cond_log_type(None, None, None, None, None)] * len

        def get_filename(self, idx=0):
            return self.log[idx].file_path.name

    class ExecResult:
        # 0: 処理継続
        Hold = 0
        # 1以上: 値分だけ適用ルール解除して再判定を行う
        Reset_1 = 1
        Reset_2 = 2
        Rest_99 = 99
        # -1以下: 特殊コマンド
        # 全条件を解除する
        ResetAll = -1
        # 現ファイルの解析は中断して次のファイルの解析に移行する
        NextFile = -2
        # 同じ行を再解析する
        OneMore = -3

    FileChangeFunc = Callable[[pathlib.Path], bool]
    ExecFunc = Callable[[int, str, cond_log_list], int]

    class adapter:
        def __init__(self, file_change, exec) -> None:
            self.file_change: gram.FileChangeFunc = file_change
            self.exec: gram.ExecFunc = exec

    def __init__(self, cond: any, adapts) -> None:
        """
        適用ルールとして正規表現をlistで持つ。
        listを順にチェックし、すべての正規表現にマッチしたら処理の適用を開始する。
        適用処理がルール終了を返したら、適用ルールのチェックから再開する。
        """
        # 適用ルール
        temp_list = []
        self.cond_name = None
        # 適用ルール初期化
        # listで保持する
        match cond:
            case None:
                # 条件なし
                temp_list = []
            case str():
                # str単独であればlist化してセット
                temp_list = [cond]
            case list():
                # listであればそのままセット
                temp_list = cond
            case tuple():
                # tupleでは[0]にルール名称、[1]にルールが格納されている
                self.cond_name = cond[0]
                # ↑と同じ処理。共通化したい
                match cond[1]:
                    case None:
                        # 条件なし
                        temp_list = []
                    case str():
                        # str単独であればlist化してセット
                        temp_list = [cond[1]]
                    case list():
                        # listであればそのままセット
                        temp_list = cond[1]

        # 正規表現文字列を事前にコンパイルしておく
        self.cond_list: List[re.Pattern] = []
        for reg_str in temp_list:
            self.cond_list.append(re.compile(reg_str))

        # 適用処理
        # 適用処理初期化
        self.adapts: List[any] = []
        match adapts:
            case list():
                self.adapts = adapts
            case _:
                self.adapts.append(adapts)

        # 親適用条件ログ
        self.parent_log = None

        # 共通データ初期化
        self.cond_pos = 0
        self.cond_len = len(self.cond_list)
        self.cond_log = gram.cond_log_list(self.cond_len, None)
        self.cond_state = False
        # 子要素同時有効化設定
        self.enable_parallel = False
        self.is_adapt_active = False

        # root要素設定
        # インスタンス作成時点でrootフラグはtrueにする。
        # 子要素に対してrootフラグを下す処置を行うことで、
        # 親を持たないroot要素だけrootフラグが残る。
        self.root = True
        for adapt in self.adapts:
            match adapt:
                case gram():
                    adapt.set_child(self.cond_log)
                case _:
                    pass
        # change_fileコールバック
        self.file_change_cb = None
        #
        self.encoding = "cp932"

    def set_child(self, parent):
        self.root = False
        self.cond_log.parent = parent

    def file_change(self, p: pathlib.Path):
        """
        新規ファイルの解析を開始するときにコールされる
        """
        # コールバック実行
        if self.file_change_cb is not None:
            if self.file_change_cb(p):
                self.cond_pos = 0
                self.cond_state = False
        # 全gramを初期化
        self.reset_gram(self)

    def reset_gram(self, node):
        node: gram
        # 自分をリセット
        node.reset_cond()
        #
        for adapt in node.adapts:
            match adapt:
                case gram():
                    self.reset_gram(adapt)
                case _:
                    pass

    def set_root(self):
        pass

    """
    parent要素側処理
    """

    def analyze(self, path: pathlib.Path, encoding="cp932", fc: FileChangeFunc = None):
        """
        analyzeがコールされたノードはルールを無視してadaptsの判定だけ実施
        """
        # 処置対象フォルダが存在しなければ終了
        if not path.exists():
            raise Exception(f"Not Exist file/dir: {str(path)}")

        # 処理の最初にroot要素調整

        self.encoding = encoding
        self.file_change_cb = fc

        if path.is_dir():
            self.analyze_dir(path)
        elif path.is_file():
            self.analyze_file(path)
        else:
            raise Exception(f"path is not file/dir: {str(path)}")

    def analyze_dir(self, path: pathlib.Path):
        for p in path.glob("**/*"):
            self.analyze_file(p)

    def analyze_file(self, path: pathlib.Path):
        # 新規ファイル解析開始
        self.file_change(path)

        # ファイルを開いて1行ずつ処理する
        with path.open("r", encoding=self.encoding) as ifs:
            for line_no, line in enumerate(ifs.readlines()):
                is_loop = True
                while is_loop:
                    is_loop = False

                    # 解析実施
                    result = self.analyze_line(path, line_no, line)
                    # 実行結果チェック
                    match result:
                        case gram.ExecResult.NextFile:
                            # ループ中断して次のファイルへ移行
                            break
                        case gram.ExecResult.OneMore:
                            # 何もしない
                            is_loop = True
                            pass
                        case _:
                            # 何もしない
                            pass

    def analyze_line(self, path: pathlib.Path, line_no: int, line: str) -> int:
        """
        適用ルールチェック
        最下位に無条件成立ノードを置きたいため、
          * 上位条件が先に成立したら下位条件は不成立とする
          * 下位条件が成立しても上位条件は判定を継続する
        適用条件成立状況は is_adapt_active に記憶する。
        処理実行後のgram終了判定は戻り値で判定する。
        """
        if line_no == 81:
            pass
        is_active = False
        adapt_result = gram.ExecResult.Hold
        for adapt in self.adapts:
            is_loop = True
            while is_loop:
                is_loop = False
                # 処理実施
                match adapt:
                    case gram():
                        if not adapt.cond_state:
                            # 適用条件未成立時は条件判定実施
                            # gramノードは条件判定
                            if is_active:
                                # 上位条件が成立している場合は不成立設定
                                adapt.reset_cond()
                            else:
                                # 上位条件が成立していない場合は通常の条件判定
                                is_active = adapt.exec_cond(path, line_no, line)
                        else:
                            # 適用条件成立後、次の周期から処理実施
                            is_active = True
                            adapt_result = adapt.exec_adapt(path, line_no, line)
                            # 戻り値で指定された処理を実施
                            match adapt_result:
                                case val if val > 0:
                                    # 通常の解除ケース
                                    adapt_result -= 1
                                    adapt.reset_cond()
                                case gram.ExecResult.ResetAll:
                                    adapt.reset_cond()
                                case gram.ExecResult.NextFile:
                                    # 最上位まで伝搬させる
                                    pass
                                case gram.ExecResult.OneMore:
                                    # 条件クリアして再解析
                                    adapt.reset_cond()
                                    is_loop = True
                                    is_active = False
                                    # 1回ループしたらクリア
                                    adapt_result = gram.ExecResult.Hold
                                case _:
                                    # 0, 上記以外は何もしない
                                    pass

                    case _:
                        if not is_active:
                            # gram以外のノードはExecFuncを想定
                            is_active = True
                            adapt_result = adapt(line_no, line, self.cond_log)
                            # 生コールバック関数の場合、
                            # 値をそのまま上位に渡して、上位で処理を行う

        self.is_adapt_active = is_active

        return adapt_result

    """
    child要素側処理
    """

    def reset_cond(self):
        # ルール適用状態リセット
        self.cond_pos = 0
        self.cond_state = False
        self.is_adapt_active = False

    def exec_cond(self, path: pathlib.Path, line_no: int, line: str) -> bool:
        # すでに条件成立済みなら終了
        if self.cond_state:
            return

        # ルール適用判定
        check = False
        m = self.cond_list[self.cond_pos].match(line)
        if m is not None:
            # ルール適用OKのとき
            # 正規表現マッチ結果を保存
            self.cond_log.log[self.cond_pos] = gram.cond_log_type(path, line_no, line, m, self.cond_name)
            # ルール適用位置を更新
            self.cond_pos += 1
            # 全ルールのマッチ成功したらTrueを返す
            if self.cond_pos >= self.cond_len:
                check = True
        else:
            # ルール適用NGのとき
            # ルール適用リセット
            self.reset_cond()
        # 結果を返す
        self.cond_state = check
        return self.cond_state

    def exec_adapt(self, path: pathlib.Path, line_no: int, line: str) -> int:
        # 再帰的に子要素gramの処理を実行
        return self.analyze_line(path, line_no, line)

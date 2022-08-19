import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

#from pyAnlexed import (pyAnlexed)
#from pyAnlexed.gram import gram
from pyAnlexed import (gram, analyze)

import enum
import pathlib
import re
from typing import Dict

path_str = "./ptn1"
path_str = os.path.join(os.path.dirname(__file__), path_str)
tgt_path = pathlib.Path(path_str)


class comment_map:

	def __init__(self) -> None:
		self.var_map: Dict[comment_map.node] = {}				# 変数マップ
		self.type_map: Dict[comment_map.node] = {}				# 型(主に構造体)マップ

		# print用定義
		self.indent = '  '

	class node:
		class TAG(enum.Enum):
			base = enum.auto()			# primitive type
			array = enum.auto()			# array
			struct = enum.auto()		# struct
			union = enum.auto()			# union
			func = enum.auto()			# function type

		def __init__(self) -> None:
			self.tag = None				# 変数タイプタグ
			# 変数情報
			self.name = None			# 変数名
			self.comment = None			# コメント
			# 型情報
			self.member = {}			# struct/union/classにおけるメンバ情報
			self.bit_size = None		# ビットフィールド宣言時のビットサイズ

	def print(self):
		prev_file = ""
		# 変数出力
		print("// var_info")
		for item in self.var_map.items():
			file = item[0][0]
			name = item[0][1]
			# ファイル名
			if file != prev_file:
				print(f'// file: {file}')
			# 情報出力
			self.print_impl(item[1])
			# 前回値更新
			prev_file = file

		# 型出力
		print("")
		print("// type_info")
		for item in self.type_map.items():
			file = item[0][0]
			name = item[0][1]
			# ファイル名
			if file != prev_file:
				print(f'// file: {file}')
			# 情報出力
			self.print_impl(item[1])
			# 前回値更新
			prev_file = file

	def print_impl(self, n: node, parent_name="", depth=0):
		# 共通情報作成
		name = n.name
		comment = n.comment
		bit_size = n.bit_size
		if name is None:
			name = '<unnamed>'
		if comment is None:
			comment = '<uncommented>'
		if bit_size is not None:
			name += f' ({bit_size} bit)'

		# tag毎に処理
		match n.tag:
			case comment_map.node.TAG.base:
				# 通常変数
				print(f'{(self.indent*depth)+parent_name+name:40} : {comment}')

			case comment_map.node.TAG.struct:
				# 変数名
				name = parent_name + name
				print(f'{(self.indent*depth)+"<struct>"+name:40} : {comment}')
				# member
				for mem in n.member.items():
					mem_node = mem[1]
					self.print_impl(mem_node, name+".", depth+1)

			case _:
				pass


class comment_get:

	# 有効なprocを格納
	class mode(enum.Enum):
		null = enum.auto()
		proc1 = enum.auto()
		proc2 = enum.auto()
		proc3 = enum.auto()

	# 解析中のC grammar
	class state(enum.Enum):
		null = enum.auto()
		typedef_struct = enum.auto()

	def __init__(self, tgt_path: pathlib.Path) -> None:
		# 相対パスを取るようの探索開始パス
		self.tgt_path = tgt_path
		self.rel_path = None
		# コメント情報マップ
		self.comment_map = comment_map()

		self.comment = None
		# 正規表現定義
		# 行にコメントのみ
		self.str_comment_var_name = r"^\s*//\s*(.+)$"
		# struct
		# nest=0 : 最上位構造体定義
		self.str_struct = r"^\s*(?:(typedef)\s+)?(?:struct|union)\s+([a-zA-Z0-9_]+)?\s*(?:{?\s*)$"
		# next=1~ : 構造体内構造体定義
		# 1行で記述するケース
		self.str_struct_inner_1 = r"^\s*(?:struct|union)\s+(?:([a-zA-Z0-9_]+)\s+)?{\s*$"
		# 改行を入れてカッコを次行にするケース。空行を入れるケースは無視する。
		self.str_struct_inner_2_1 = r"^\s*(?:struct|union)\s+(?:([a-zA-Z0-9_]+)\s+)?$"
		self.str_struct_inner_2_2 = r"^\s*{\s+$"
		# 構造体member
		self.str_struct_member = r"[^}]+\s+([a-zA-Z0-9_]+)\s*(?:\:\s*(\d+)\s*)?;\s*(?:(})\s*([a-zA-Z0-9_]+)?\s*;\s*)?//\s*(.*)$"
		self.re_struct_member = re.compile(self.str_struct_member)
		# 構造体終了
		self.str_strunt_end = r"^\s*}\s*(?:([a-zA-Z0-9_]+)\s*)?;\s*(?://\s*(.*))?.*$"
		self.re_strunt_end = re.compile(self.str_strunt_end)

		# 変数宣言
		# 部品
		#s_type_spec_1 = r"(?:(?:unsigned|signed)\s+)?(?:char|short|int|long|long\s+long)"
		#s_type_spec_2 = r"(?:struct|union)\s+[a-zA-Z0-9_]+"
		#s_type_spec_win32api = r"(?:BOOL|BYTE|CHAR|WORD|SHORT|DWORD|ULONG|LONG|ULONGLONG|LONGLONG)"
		#s_type_sq = r"(?:const|restrict|volatile|static|extern)"
		# 結合
		#self.str_type = rf"^\s*(?:{s_type_sq}\s+)*"
		# 簡略版
		s_id = r'[a-zA-Z_][a-zA-Z0-9_]+'
		self.str_var = fr"^\s*.*?({s_id})\s*(?:=\s*[a-zA-Z0-9_]+\s*)?;\s*(?://\s*(.*))?.*$"
		self.re_var = re.compile(self.str_var)

		# 解析バッファ
		# struct定義のネストは2つまで許可
		self.log_struct_nest = 2
		self.log_member = []		# メンバ変数ログ
		self.log_nest = []			# inner構造体ログ
		for i in range(self.log_struct_nest+1):
			self.log_member.append([])
			self.log_nest.append([])

	def file_change(self, p:pathlib.Path) -> bool:
		self.rel_path = p.relative_to(self.tgt_path)
		print(f"file: {str(p)}")

	def proc1(self, line_no:int, line:str, cond_log:gram.cond_log_list) -> int:
		line = line.strip()
		print(f"  proc1: {line}")
		return 0

	def proc_global_var(self, line_no:int, line:str, cond_log:gram.cond_log_list) -> int:
		"""
		global空間での変数宣言
		"""
		line = line.strip()

		# 変数チェック
		m = self.re_var.search(line)
		if m is not None:
			# [0]=変数名, [1]=コメント
			parts = m.groups()
			# 新規ノード作成
			node = comment_map.node()
			node.tag = comment_map.node.TAG.base
			node.name = parts[0]
			node.comment = parts[1]
			# 変数登録
			self.comment_map.var_map[(self.rel_path,node.name)] = node

	def proc_struct_member_0(self, line_no:int, line:str, cond_log:gram.cond_log_list) -> int:
		"""
		struct/union member取得: nest=0
		"""
		# nest=0で解析を行う
		line = line.strip()
		result = self.proc_struct_member_impl(line_no, line, cond_log, 0)
		if result is not None:
			# comment_mapが返されたら解析終了
			# 制御comment_mapに値を反映
			for node in result.type_map.items():
				self.comment_map.type_map[node[0]] = node[1]
			for node in result.var_map.items():
				self.comment_map.var_map[node[0]] = node[1]
			# 処理終了
			return 99

		# 処理継続
		return 0

	def proc_struct_member_1(self, line_no:int, line:str, cond_log:gram.cond_log_list) -> int:
		"""
		struct/union member取得: nest=1
		"""
		# nest=1で解析を行う
		line = line.strip()
		result = self.proc_struct_member_impl(line_no, line, cond_log, 1)
		if result is not None:
			# comment_mapが返されたら解析終了
			# nestしているので解析結果を上位の解析に渡す
			# inner構造体なので変数宣言が前提とみなして、
			# 変数情報のみ展開する
			for node in result.var_map.items():
				self.log_nest[1].append(node[1])
			# 処理終了
			return 1

		# 処理継続
		return 0

	def proc_struct_member_impl(self, line_no:int, line:str, cond_log:gram.cond_log_list, nest:int) -> comment_map | None:
		"""
		struct/union member取得
		nestにより何段目の構造体宣言かを指定する。
		構造体宣言完了時には収集した情報を一時変数に格納して返す。
		"""
		temp_map = comment_map()

		# 共通フラグ
		finish = False
		post_name = None	# 構造体宣言
		comment = None

		# メンバ変数チェック
		m = self.re_struct_member.search(line)
		if m is not None:
			parts = m.groups()
			# 終了チェック
			if parts[2] is None:
				# parts[2]がNoneのときは通常のメンバ変数宣言
				# [0]=変数名, [4]=コメント, [1]=bitfieldサイズ
				self.log_member[nest].append((parts[0], parts[4], parts[1]))
			else:
				# parts[2]がNoneでない＝}が出現したとき
				# このときのparts[4]はメンバ変数に対するコメントではない
				# こんな書き方はしないと思うが一応…
				self.log_member[nest].append((parts[0], None, None))
				# }の出現により構造体宣言終了
				finish = True
				# 構造体宣言の後置識別子情報
				# parts[2]がNoneでない＝}が出現したときしかありえない
				post_name = parts[3]
				comment = parts[4]

		# 構造体終了チェック
		m = self.re_strunt_end.search(line)
		if m is not None:
			parts = m.groups()
			# }の出現により構造体宣言終了
			finish = True
			# 構造体宣言の後置識別子情報
			post_name = parts[0]
			comment = parts[1]

		# 終了判定
		if finish:
			# コメント情報収集
			# 新規構造体用ノード作成
			node = comment_map.node()
			node.tag = comment_map.node.TAG.struct
			# 収集したメンバー情報を追加する
			# self.log_member[nest]には通常変数が入っている
			for mem in self.log_member[nest]:
				# メンバーノード作成
				mem_node = comment_map.node()
				mem_node.tag = comment_map.node.TAG.base
				mem_node.name = mem[0]
				mem_node.comment = mem[1]
				mem_node.bit_size = mem[2]
				# メンバー登録
				node.member[mem_node.name] = mem_node
			# self.log_nest[nest+1]にinner構造体情報を格納している
			for is_mem in self.log_nest[nest+1]:
				is_mem: comment_map.node
				node.member[is_mem.name] = is_mem

			# 前提条件の条件マッチ状況から情報取得
			p_log = None
			if cond_log.parent is not None and len(cond_log.parent.log) > 0:
				# parentが存在しているとき、
				# 構造体宣言直前に記載されたコメント情報
				p_log = cond_log.parent.log[0].match.groups()
				p_name = cond_log.parent.log[0].name
				if p_name == "前置コメント":
					node.comment = p_log[0]
			# 1段目のメンバーなので直前のマッチ結果から構造体情報取得
			log_m = cond_log.log[0].match
			inf = log_m.groups()
			# "struct XXX"の XXX をここでは構造体名として登録する
			# Noneであれば無名という意味でNoneを入れておく
			if len(inf) > 1:
				node.name = inf[1]
			# 無名構造体でないとき、その名前でcomment_mapに登録
			if node.name is not None:
				temp_map.type_map[(self.rel_path,node.name)] = node
			# コメントがあれば構造体の名称となる
			# 前知コメントがあればそちらを優先する
			if comment is not None and node.comment is None:
				node.comment = comment
			# 無名構造体の場合、
			# typedefであれば後置名称を名前として問題なし
			# 変数宣言の場合も、この変数以外は参照できないので名前更新して記憶していい
			if node.name is None:
				node.name = post_name
			# 構造体宣言の後ろに記載された識別子の処置
			# typedef設定のときは構造体定義の後ろの識別子は型名
			if inf[0] is not None:
				# 型登録
				temp_map.type_map[(self.rel_path,post_name)] = node
			else:
				# 変数登録
				temp_map.var_map[(self.rel_path,post_name)] = node
			# 処理終了
			self.log_member[nest] = []
			self.log_nest[nest+1] = []
			return temp_map

		# 処理継続
		return None


	def proc3(self, line_no:int, line:str, cond_log:gram.cond_log_list) -> int:
		line = line.strip()
		print(f"  proc3: {line_no+1}: {line}")

		#if line == "":
		#	return False
		return 0

	def proc4(self, line_no:int, line:str, cond_log:gram.cond_log_list) -> int:
		line = line.strip()
		print(f"  proc4: {line_no+1}: {line}")
		return 0

adapter = comment_get(tgt_path)

# 作成ルールより深いstruct定義ネストがあれば警告を出す
def unexpected_struct_def_nested_func(line_no:int, line:str, cond_log:gram.cond_log_list):
	print(f"unexpected struct def nested: {cond_log.get_filename()} :{line_no}: {line}")
	return 0

rule_unexpected_struct_def_nested_1 = gram(
	adapter.str_struct_inner_1,
	unexpected_struct_def_nested_func
)
rule_unexpected_struct_def_nested_2 = gram(
	[
		adapter.str_struct_inner_2_1,
		adapter.str_struct_inner_2_2,
	],
	unexpected_struct_def_nested_func
)


rule = gram(
	None,
	[
		gram(
			# 適用条件
			("前置コメント", r"^\s*//\s*(.+)$"),
			# 処理内容
			[
				# 構造体
				gram(
					adapter.str_struct,
					[
						# member
						# inner構造体
						gram(
							adapter.str_struct_inner_1,
							[
								# 3段階目のstructが出てきたらwarning
								rule_unexpected_struct_def_nested_1,
								rule_unexpected_struct_def_nested_2,
								# member変数
								adapter.proc_struct_member_1
							]
						),
						gram(
							[
								adapter.str_struct_inner_2_1,
								adapter.str_struct_inner_2_2,
							],
							[
								# 3段階目のstructが出てきたらwarning
								rule_unexpected_struct_def_nested_1,
								rule_unexpected_struct_def_nested_2,
								# member変数
								adapter.proc_struct_member_1
							]
						),
						# member変数
						adapter.proc_struct_member_0
					]
				),
				adapter.proc3
			]
		),
		# 構造体_前置コメントなし
		gram(
			adapter.str_struct,
			[
				# member
				# inner構造体
				gram(
					adapter.str_struct_inner_1,
					[
						# 3段階目のstructが出てきたらwarning
						rule_unexpected_struct_def_nested_1,
						rule_unexpected_struct_def_nested_2,
						# member変数
						adapter.proc_struct_member_1
					]
				),
				gram(
					[
						adapter.str_struct_inner_2_1,
						adapter.str_struct_inner_2_2,
					],
					[
						# 3段階目のstructが出てきたらwarning
						rule_unexpected_struct_def_nested_1,
						rule_unexpected_struct_def_nested_2,
						# member変数
						adapter.proc_struct_member_1
					]
				),
				# member変数
				adapter.proc_struct_member_0
			]
		),
		adapter.proc_global_var
	]
)
rule.analyze(tgt_path, 'utf8', adapter.file_change)
adapter.comment_map.print()

"""
rule = gram(
	# 適用条件
	None,
	# 処理内容
	[
		gram(
			# 適用条件
			adapter.re_comment_var_name,
			# 処理内容
			[ adapter.file_change, adapter.proc2 ]
		),
		gram(
			# 適用条件
			[
				r"/////////////////////////////////",
				r"// 関数ヘッダ"
			],
			# 処理内容
			[ adapter.file_change, adapter.proc3 ]
		),
		gram(
			# 適用条件
			None,
			# 処理内容
			[ adapter.file_change, adapter.proc1 ]
		),
	]
)

path_str = "./ptn1"
path_str = os.path.join(os.path.dirname(__file__), path_str)
analyze(pathlib.Path(path_str), rule, 'utf8', adapter.file_change)
"""

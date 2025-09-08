# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function

"""
#########################################################
#                                                       #
#  Universal Logger Module                              #
#  Version: 1.0                                         #
#  Created by Lululla (https://github.com/Belfagor2005) #
#  License: CC BY-NC-SA 4.0                             #
#  https://creativecommons.org/licenses/by-nc-sa/4.0    #
#  Last Modified: 2025-05-27                            #
#                                                       #
#  Credits:                                             #
#  - Original concept by Lululla                        #
#  Usage of this code without proper attribution        #
#  is strictly prohibited.                              #
#  For modifications and redistribution,                #
#  please maintain this credit header.                  #
#########################################################
"""

import sys
import threading
from os import makedirs, remove, rename
from os.path import join, exists, getsize
from time import strftime
from io import StringIO

# Manteniamo le variabili e funzioni con lo stesso nome
logfile = StringIO()
mutex = threading.Lock()

# Creiamo un'istanza del logger
_logger_instance = None


def write(data):
	"""Funzione write mantenuta per compatibilità"""
	# Manteniamo il comportamento originale per thread-safety
	mutex.acquire()
	try:
		if logfile.tell() > 8000:
			logfile.seek(0)
		logfile.write(data)
	finally:
		mutex.release()
	
	# Usiamo il nuovo logger per l'output
	if data.strip():  # Ignora righe vuote
		logger = _get_logger()
		logger.info(data.rstrip())


def getvalue():
	"""Funzione getvalue mantenuta per compatibilità"""
	mutex.acquire()
	try:
		pos = logfile.tell()
		head = logfile.read()
		logfile.seek(0)
		tail = logfile.read(pos)
	finally:
		mutex.release()
	return head + tail


class ColoredLogger:
	LEVELS = {
		"DEBUG": ("\033[92m", "[DEBUG]"),           # green
		"INFO": ("\033[97m", "[INFO] "),            # white
		"WARNING": ("\033[93m", "[WARN] "),         # yellow
		"ERROR": ("\033[91m", "[ERROR]"),           # red
		"CRITICAL": ("\033[95m", "[CRITICAL]"),     # magenta
	}
	END = "\033[0m"
	_instances = {}
	_lock = threading.Lock()
	
	# Aggiungi questa variabile di classe
	SUPPORTS_COLOR = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

	def __new__(cls, log_path=None, plugin_name="generic", clear_on_start=True, max_size_mb=1):
		instance_key = f"{log_path}_{plugin_name}"

		if instance_key not in cls._instances:
			with cls._lock:
				if instance_key not in cls._instances:
					instance = super().__new__(cls)
					cls._instances[instance_key] = instance
					instance._initialize(log_path, plugin_name, clear_on_start, max_size_mb)

		return cls._instances[instance_key]

	def log(self, level, message):
		if not hasattr(self, '_initialized'):
			return

		color, label = self.LEVELS.get(level.upper(), ("", "[LOG] "))
		timestamp = strftime("%Y-%m-%d %H:%M:%S")
		formatted_message = f"{timestamp} {self.plugin_name} {label} {message}"

		# Modifica qui: usa i colori solo se supportati
		if self.SUPPORTS_COLOR:
			print(f"{timestamp} {self.plugin_name} {label} {color}{message}{self.END}")
		else:
			print(f"{timestamp} {self.plugin_name} {label} {message}")

		if self.log_file:
			self._write_to_file(formatted_message)
			self._check_rotation()

	def _initialize(self, log_path, plugin_name, clear_on_start, max_size_mb):
		self.plugin_name = plugin_name
		self.max_size_mb = max_size_mb

		if log_path:
			if not exists(log_path):
				try:
					makedirs(log_path)
				except Exception as e:
					print(f"Error creating log directory {log_path}: {e}")
					log_path = None

		if log_path:
			self.log_file = join(log_path, f"{plugin_name}.log")
			if clear_on_start and exists(self.log_file):
				try:
					remove(self.log_file)
				except Exception as e:
					print(f"Error removing old log file: {e}")
		else:
			self.log_file = None

		self._initialized = True

	def _write_to_file(self, message):
		try:
			with open(self.log_file, "a") as f:
				f.write(message + "\n")
				f.flush()
		except Exception as e:
			print(f"[LOG ERROR] Cannot write to {self.log_file}: {e}")

	def _check_rotation(self):
		try:
			if not exists(self.log_file):
				return

			file_size = self._get_file_size_mb()
			if file_size > self.max_size_mb:
				self._rotate_logs()
		except Exception as e:
			print(f"[LOG ERROR] Rotation check failed: {e}")

	def _get_file_size_mb(self):
		try:
			return getsize(self.log_file) / (1024 * 1024)
		except:
			return 0

	def _rotate_logs(self):
		try:
			import glob
			base_name = self.log_file
			pattern = f"{base_name}.*"

			backups = sorted(glob.glob(pattern), reverse=True)

			for old_backup in backups[4:]:
				try:
					remove(old_backup)
				except:
					pass

			for i in range(min(len(backups), 4), 0, -1):
				old_name = f"{base_name}.{i}" if i > 1 else base_name
				new_name = f"{base_name}.{i + 1}"

				if exists(old_name):
					try:
						rename(old_name, new_name)
					except:
						pass

		except Exception as e:
			print(f"[LOG ERROR] Log rotation failed: {e}")

	def debug(self, message, *args):
		self.log("DEBUG", message % args if args else message)

	def info(self, message, *args):
		self.log("INFO", message % args if args else message)

	def warning(self, message, *args):
		self.log("WARNING", message % args if args else message)

	def error(self, message, *args):
		self.log("ERROR", message % args if args else message)

	def critical(self, message, *args):
		self.log("CRITICAL", message % args if args else message)

	def exception(self, message, *args):
		import traceback
		exc_info = sys.exc_info()
		traceback_text = ''.join(traceback.format_exception(*exc_info))
		full_message = f"{message % args if args else message}\n{traceback_text}"
		self.log("ERROR", full_message)

	def show_message(self, session, text, timeout=5):
		try:
			from Screens.MessageBox import MessageBox
			session.openWithCallback(
				self._message_closed,
				MessageBox,
				text=text,
				type=MessageBox.TYPE_INFO,
				timeout=timeout
			)
		except Exception as e:
			self.error("Cannot show message: %s", e)

	def _message_closed(self, ret=None):
		self.debug("MessageBox closed")


def get_logger(log_path=None, plugin_name="xmltv-import", clear_on_start=True, max_size_mb=1):
	return ColoredLogger(
		log_path=log_path,
		plugin_name=plugin_name,
		clear_on_start=clear_on_start,
		max_size_mb=max_size_mb
	)


def _get_logger():
	"""Funzione interna per ottenere l'istanza del logger"""
	global _logger_instance
	if _logger_instance is None:
		_logger_instance = ColoredLogger(
			log_path='/tmp',  # None,
			plugin_name="XMLTV-Import",
			clear_on_start=False,
			max_size_mb=1
		)
	return _logger_instance


class LogFile:
	"""Classe che emula un file object per compatibilità con print(..., file=log)"""
	def __init__(self):
		self.logger = _get_logger()
	
	def write(self, data):
		if data.strip():  # Ignora righe vuote o solo newline
			self.logger.info(data.rstrip())
	
	def flush(self):
		pass


log = LogFile()

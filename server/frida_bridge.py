import threading
import json
import os
import time
import traceback
from colorama import Fore, Style
import config
from auth_client import AuthClient, AuthenticationError
from utils import get_time, _parse_socketio

def authenticate_mobile():
	if not config.SERVER_URL or not config.SERVER_API_KEY:
		print(
			f'{get_time()} {Fore.RED}Missing MENTALIST_SERVER_URL or MENTALIST_SERVER_API_KEY{Style.RESET_ALL}',
			flush=True
		)

		return False
	
	try:
		print(
			f'{get_time()} {Fore.YELLOW}Authenticating with Mentalist Server...{Style.RESET_ALL}',
			flush=True
		)

		config.auth_client = AuthClient(config.SERVER_URL, config.SERVER_API_KEY)
		permissions, user_id = config.auth_client.authenticate()
		
		print(
			f'{get_time()} {Fore.GREEN}Authentication successful! User #{user_id}{Style.RESET_ALL}',
			flush=True
		)

		if not config.auth_client.check_module_permission('tracker'):
			print(
				f'{get_time()} {Fore.RED}Access Denied: No TRACKER permission{Style.RESET_ALL}',
				flush=True
			)

			return False
		
		print(
			f'{get_time()} {Fore.GREEN}[TRACKER] access verified{Style.RESET_ALL}',
			flush=True
		)
		
		return True
	except AuthenticationError as e:
		print(
			f'{get_time()} {Fore.RED}Authentication Failed: {e}{Style.RESET_ALL}',
			flush=True
		)

		return False
	except Exception as e:
		print(
			f'{get_time()} {Fore.RED}Unexpected auth error: {e}{Style.RESET_ALL}',
			flush=True
		)

		return False

def on_message(message, data):
	time_str = get_time()

	try:
		if message['type'] == 'send':
			payload = message['payload']

			if isinstance(payload, str):
				try:
					payload = json.loads(payload)
				except json.JSONDecodeError:
					print(
						f'{time_str} {Fore.WHITE}[Frida Agent] {Style.RESET_ALL}Raw Message: {payload}',
						flush=True
					)

					return

			if payload.get('type') == 'ws_message':
				direction = payload.get('direction', 'UNKNOWN')
				data_content = payload.get('data', 'N/A')
				data_type = payload.get('dataType', 'Unknown')

				try:
					if data_type == 'String' and isinstance(data_content, str):
						msg_type = 'UNKNOWN'

						if data_content.startswith('0'):
							msg_type = 'CONNECT'

						elif data_content.startswith('1'):
							msg_type = 'DISCONNECT'

						elif data_content.startswith('2'):
							msg_type = 'PING'

						elif data_content.startswith('3'):
							msg_type = 'PONG'

						elif data_content.startswith('40'):
							msg_type = 'NAMESPACE_CONNECT'

						elif data_content.startswith('41'):
							msg_type = 'NAMESPACE_DISCONNECT'

						elif data_content.startswith('42'):
							msg_type = 'EVENT'

						elif data_content.startswith('43'):
							msg_type = 'ACK'

						if direction == 'INBOUND':
							print(
								f'{time_str} {Fore.CYAN}[WS IN:{msg_type}] {data_content[:200]}{Style.RESET_ALL}',
								flush=True
							)

						else:
							print(
								f'{time_str} {Fore.MAGENTA}[WS OUT:{msg_type}] {data_content[:200]}{Style.RESET_ALL}',
								flush=True
							)

							if msg_type == 'EVENT' and '"game-commit-suicide"' in data_content:
								print(f'{get_time()} {Fore.YELLOW}[Game] Village flee detected. Resetting state...{Style.RESET_ALL}', flush=True)

								if backend and config.backend.tracker:
									config.backend.tracker.reset()
									banner(f'Tracker {Fore.YELLOW}/ with {Fore.RED}Mastermind{Fore.RESET}' if config.backend.mastermind and config.backend.mastermind.profiles else 'Tracker')
				except Exception as log_err:
					print(
						f'{time_str} {Fore.RED}[WS Log Error] {log_err}{Style.RESET_ALL}',
						flush=True
					)

				try:
					if data_type == 'String' and isinstance(data_content, str):
						try:
							config.backend.process_ws(direction, data_content)
						except Exception as backend_err:
							print(
								f'{time_str} {Fore.RED}[Backend Process Error] {backend_err}{Style.RESET_ALL}',
								flush=True
							)

							traceback.print_exc()

						try:
							env = config.backend.tracker._parse_socketio_envelope(data_content)

							if env:
								evt, p = env
								event_color = Fore.GREEN

								if 'chat' in evt:
									event_color = Fore.CYAN

								elif 'killed' in evt or 'vote' in evt:
									event_color = Fore.YELLOW

								elif 'role' in evt:
									event_color = Fore.MAGENTA

								print(
									f'{time_str} {event_color}[WS Event] {evt}{Style.RESET_ALL}',
									flush=True
								)

								try:
									if evt in [
										'player-joined-and-equipped-items',
										'player-disconnected'
									]:
										name = ''

										if (
											evt == 'player-joined-and-equipped-items'
											and p
											and 'player' in p
										):
											name = p['player'].get(
												'username', 'Unknown'
											)

										elif evt == 'player-disconnected' and p:
											pid = p.get('id')
											num = config.backend.tracker.num_by_id.get(pid)

											if num and 1 <= num <= 16:
												player = config.backend.tracker.PLAYERS[num - 1]

												name = player.get('name', 'Unknown')

										print(
											f'{time_str} {Fore.GREEN}  └─ Player: {name}{Style.RESET_ALL}',
											flush=True
										)

									elif evt == 'game:chat-public:msg' and p:
										author_id = p.get('authorId', 'system')
										num = config.backend.tracker.num_by_id.get(author_id)
										author_name = 'system'

										if num and 1 <= num <= 16:
											player = config.backend.tracker.PLAYERS[num - 1]
											author_name = player.get('name', 'system')

										msg_text = p.get('msg', '')

										print(
											f'{time_str} {Fore.CYAN}  └─ {author_name}: {msg_text}{Style.RESET_ALL}',
											flush=True
										)

									elif evt == 'game-day-vote-set' and p:
										voter_id = p.get('voterId')
										target_id = p.get('targetPlayerId')
										voter_num = config.backend.tracker.num_by_id.get(voter_id)
										target_num = config.backend.tracker.num_by_id.get(target_id)
										voter_name = '?'
										target_name = '?'

										if voter_num and 1 <= voter_num <= 16:
											voter_name = config.backend.tracker.PLAYERS[
												voter_num - 1
											].get('name', '?')

										if target_num and 1 <= target_num <= 16:
											target_name = config.backend.tracker.PLAYERS[
												target_num - 1
											].get('name', '?')

										count = p.get('count', '?')

										print(
											f'{time_str} {Fore.YELLOW}  └─ {voter_name} → {target_name} (total: {count}){Style.RESET_ALL}',
											flush=True
										)

									elif evt == 'game-players-killed' and p:
										victims = p.get('victims', [])

										for v in victims:
											target_id = v.get('targetPlayerId')
											cause = v.get('cause', 'unknown')
											target_num = config.backend.tracker.num_by_id.get(target_id)
											target_name = '?'

											if target_num and 1 <= target_num <= 16:
												target_name = config.backend.tracker.PLAYERS[
													target_num - 1
												].get('name', '?')

											role_info_str = ''
											role_id = v.get('roleId')

											if role_id:
												role_data = config.backend.tracker.ROLES.get(role_id)

												if role_data and 'name' in role_data:
													role_info_str = f' as {role_data["name"]}'

												else:
													role_info_str = f' as {role_id}'

											print(
												f'{time_str} {Fore.RED}  └─ ☠ {target_name} ({cause}){role_info_str}{Style.RESET_ALL}',
												flush=True
											)

									elif evt == 'game-role-revealed' and p:
										pid = p.get('playerId')
										role_id = p.get('roleId')
										num = config.backend.tracker.num_by_id.get(pid)
										player_name = '?'

										if num and 1 <= num <= 16:
											player_name = config.backend.tracker.PLAYERS[
												num - 1
											].get('name', '?')

										print(
											f'{time_str} {Fore.MAGENTA}  └─ {player_name} revealed as {role_id}{Style.RESET_ALL}',
											flush=True
										)

									elif evt in [
										'game-started',
										'game-night-started',
										'game-day-started',
										'game-day-voting-started'
									]:
										day = p.get('day', '?') if p else '?'
										phase = p.get('phase', '') if p else ''

										print(
											f'{time_str} {Fore.YELLOW}  └─ Day {day} {phase}{Style.RESET_ALL}',
											flush=True
										)

									elif evt == 'game-settings-changed' and p:
										roles = p.get('roles', [])

										if roles:
											print(
												f'{time_str} {Fore.BLUE}  └─ Roles: {", ".join(roles[:5])}{"..." if len(roles) > 5 else ""}{Style.RESET_ALL}',
												flush=True
											)
								except Exception as detail_err:
									print(
										f'{time_str} {Fore.RED}[Event Detail Error] {detail_err}{Style.RESET_ALL}',
										flush=True
									)
						except Exception as parse_err:
							print(
								f'{time_str} {Fore.RED}[Event Parse Error] {parse_err}{Style.RESET_ALL}',
								flush=True
							)

							traceback.print_exc()

						try:
							payload_data = config.backend.build_view_data()
							config.script.exports_sync.setviewdata(json.dumps(payload_data))
						except Exception as e2:
							print(
								f'{time_str} {Fore.RED}[Render Push Error] {e2}{Style.RESET_ALL}',
								flush=True
							)
				except Exception as e:
					print(
						f'{time_str} {Fore.RED}[Backend Error] {e}{Style.RESET_ALL}',
						flush=True
					)

					traceback.print_exc()

			elif payload.get('type') == 'command':
				cmd_text = payload.get('data', '') or payload.get('text', '')

				if cmd_text:
					try:
						result = config.backend.process_command(cmd_text)
						error_msg = None

						if isinstance(result, str):
							error_msg = result

						try:
							payload_data = config.backend.build_view_data()
							config.script.exports_sync.setviewdata(json.dumps(payload_data))

							if error_msg:
								config.script.exports_sync.seterror(error_msg)

							print(
								f'{time_str} {Fore.CYAN}[Render] view data pushed after command{Style.RESET_ALL}',
								flush=True
							)
						except Exception as e2:
							print(
								f'{time_str} {Fore.RED}[Render Push Error] {e2}{Style.RESET_ALL}',
								flush=True
							)
					except Exception as e:
						error_str = str(e)

						try:
							config.script.exports_sync.seterror(error_str)
						except:
							pass

						print(
							f'{time_str} {Fore.RED}[Backend Cmd Error] {e}{Style.RESET_ALL}',
							flush=True
						)

			elif payload.get('type') == 'event':
				event_name = payload.get('event')

			elif payload.get('type') == 'predict_request':
				try:
					result = config.backend.predict()
					config.script.exports_sync.setpredictresult(result)

					print(
						f'{time_str} {Fore.GREEN}[Predict] Result sent to UI{Style.RESET_ALL}',
						flush=True
					)
				except Exception as e:
					error_str = f'Predict error: {str(e)}'

					try:
						config.script.exports_sync.setpredictresult(error_str)
					except:
						pass

					print(
						f'{time_str} {Fore.RED}[Predict Error] {e}{Style.RESET_ALL}',
						flush=True
					)

			elif payload.get('type') == 'http_request':
				try:
					method = payload.get('method', '?')
					url    = payload.get('url', '')
					print(
						f'{time_str} {Fore.WHITE}[HTTP] {method} {url[:120]}{Style.RESET_ALL}',
						flush=True
					)
				except Exception as e:
					pass

			elif payload.get('type') == 'http_headers':
				try:
					url = payload.get('url', '')
					headers = payload.get('headers', {})
					bearer = None
					cf_jwt = None
					auth = headers.get('Authorization') or headers.get('authorization')

					if auth and auth.startswith('Bearer '):
						bearer = auth.split(' ', 1)[1]

					cf_jwt_keys = ['Cf-Jwt', 'cf-jwt', 'CF-JWT']

					for key in cf_jwt_keys:
						if key in headers:
							cf_jwt = headers[key]

							break

					if bearer or cf_jwt:
						config.backend.set_auth(bearer, cf_jwt)
						if bearer:
							print(f'{time_str} {Fore.CYAN}[Auth] Bearer token captured (***{bearer[-8:]}){Style.RESET_ALL}', flush=True)
				except Exception as e:
					print(
						f'{time_str} {Fore.RED}[Backend Auth Capture Error] {e}{Style.RESET_ALL}',
						flush=True
					)

			elif payload.get('type') == 'log':
				print(
					f'{time_str} {Fore.YELLOW}[Frida Log] {payload.get("message")}{Style.RESET_ALL}',
					flush=True
				)

			else:
				print(
					f'{time_str} {Fore.WHITE}[Frida Agent] {Style.RESET_ALL}{payload}',
					flush=True
				)

		elif message['type'] == 'error':
			print(
				f'{time_str} {Fore.RED}[Frida Error] {message.get("description", "Unknown error")}{Style.RESET_ALL}',
				flush=True
			)
			print(
				f'{time_str} {Fore.RED}[Stack] {message.get("stack", "No stack trace")}{Style.RESET_ALL}',
				flush=True
			)
	except Exception as e:
		print(
			f'{time_str} {Fore.RED}[Python Error in on_message] {e}{Style.RESET_ALL}',
			flush=True
		)

		traceback.print_exc()

def poll_agent_messages():
	print(
		f'{get_time()} {Fore.CYAN}[Poller] RPC polling thread started...{Style.RESET_ALL}',
		flush=True
	)

	time.sleep(0.5)

	while not config.shutdown_event.is_set():
		try:
			messages_json = config.script.exports_sync.getqueuedmessages()

			if messages_json:
				messages_list = json.loads(messages_json)

				if messages_list:
					for msg_str in messages_list:
						try:
							frida_message_payload = json.loads(msg_str)
							frida_message_envelope = {
								'type': 'send',
								'payload': frida_message_payload,
							}
							on_message(frida_message_envelope, None)
						except Exception as inner_e:
							print(
								f'{get_time()} {Fore.RED}[Poller Inner Error] {inner_e} on msg {msg_str[:100]}{Style.RESET_ALL}',
								flush=True
							)
		except Exception as e:
			error_str = str(e).lower()

			if (
				'method not found' in error_str
				or 'unable to find method' in error_str
				or 'getqueuedmessages' in error_str
			):
				pass

			elif 'destroyed' in error_str or 'detached' in error_str:
				print(
					f'\n{get_time()} {Fore.RED}[Poller] Connection lost — game closed or detached. Shutting down.{Style.RESET_ALL}',
					flush=True
				)
				config.shutdown_event.set()
				import os as _os
				_os._exit(1)

			else:
				print(
					f'{get_time()} {Fore.RED}[Poller Error] {e}{Style.RESET_ALL}',
					flush=True
				)

		config.shutdown_event.wait(0.1)

	print(
		f'{get_time()} {Fore.CYAN}[Poller] RPC polling thread stopped.{Style.RESET_ALL}',
		flush=True
	)

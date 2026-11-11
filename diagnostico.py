"""Interfaz de solo lectura para agentes: python diagnostico.py todo --json."""
import argparse
import json
import sys
from datetime import datetime, timezone
from src.diagnostics import ROOT, status, web_status, recent_errors, redact, secret_values


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs='?', default='todo', choices=('todo', 'estado', 'web', 'errores'))
    parser.add_argument('--port', type=int, default=5050)
    parser.add_argument('--lines', type=int, default=30)
    parser.add_argument('--json', action='store_true', help='JSON compacto para herramientas')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535 or not 1 <= args.lines <= 200:
        parser.error('Usa un puerto entre 1 y 65535 y entre 1 y 200 líneas.')
    result = {'schema_version': '1.0', 'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'read_only': True}
    if args.command in ('todo', 'estado'):
        result['status'] = status()
    if args.command in ('todo', 'web'):
        result['web'] = web_status(args.port)
    if args.command in ('todo', 'errores'):
        result['logs'] = recent_errors(lines=args.lines)
    print(redact(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2), secret_values()))


if __name__ == '__main__':
    main()

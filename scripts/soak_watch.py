"""Bounded local soak-test observer. Reads test files; never calls production HA.

The run file is private local configuration. Notifications queue work only in
the user's existing Codex chat. No integrations, devices or measurements change.
"""
from collections import Counter, deque
from datetime import datetime, timezone
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import time
from zoneinfo import ZoneInfo

from verify_live_capture import check

CONTAINER = 'grid-peak-monitor-preview'


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name+'.tmp')
    fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump(value, output, ensure_ascii=False, allow_nan=False, indent=2)
        output.write('\n')
    temporary.replace(path)


def local(at):
    return datetime.fromtimestamp(at, ZoneInfo('Europe/Vienna')).isoformat(timespec='seconds')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect_test(docker):
    try:
        result = subprocess.run([docker, '--context', 'orbstack', 'inspect', CONTAINER,
            '--format', '{"state":{{json .State}},"restarts":{{.RestartCount}}}'],
            capture_output=True, text=True, timeout=15)
        if result.returncode: return {'inspection_failed': True}
        return json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return {'inspection_failed': True}


class Observer:
    def __init__(self, run_path, *, notifier=None):
        self.run_path = Path(run_path).resolve()
        self.run = json.loads(self.run_path.read_text())
        self.directory = self.run_path.parent
        self.project = Path(self.run['project']).resolve()
        self.test = self.project/'output/ha-preview-config'
        if self.run['container'] != CONTAINER or not (self.test/'.grid-peak-preview').exists():
            raise ValueError('Refusing a different test configuration')
        self.audit = self.test/'live-audit.jsonl'
        self.state_path = self.directory/'watch-state.json'
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text())
        else:
            self.state = {'offset': 0, 'samples': 0, 'counts': {}, 'records': {}, 'verified': {},
                'parse_errors': 0, 'arithmetic_errors': [], 'issues': {}, 'past_issues': [],
                'last_at': None, 'last_snapshot': None, 'max_gap_s': 0, 'valid_seconds': 0,
                'last_quality': None, 'counter_first': None, 'counter_last': None,
                'max_import_kw': 0, 'sustained_import_seen': False, 'midpoint_done': False,
                'import_run_since': None,
                'completed': False, 'completion_queued': False}
        self.buffer = deque()
        self.notifier = notifier or self.queue
        self.last_check = 0
        self.restore_buffer()

    def restore_buffer(self):
        """Rebuild a small source window after observer restart, without recounting."""
        if not self.audit.exists(): return
        offset = self.state['offset']
        with self.audit.open('rb') as source:
            left = max(0, offset-2*1024*1024)
            source.seek(left)
            data = source.read(max(0, offset-left))
        if left: data = data.split(b'\n', 1)[-1]
        for line in data.splitlines():
            try: row = json.loads(line)
            except (ValueError, UnicodeError): continue
            if row.get('calculated_at', 0) >= self.run['started_at']:
                self.buffer.append(row)
        if self.buffer:
            cutoff = self.buffer[-1]['calculated_at']-2700
            while self.buffer and self.buffer[0]['calculated_at'] < cutoff: self.buffer.popleft()

    def consume(self):
        if not self.audit.exists(): return
        with self.audit.open('rb') as source:
            source.seek(0, 2)
            if source.tell() < self.state['offset']:
                self.state['parse_errors'] += 1
                self.state['offset'] = 0
            source.seek(self.state['offset'])
            while True:
                before = source.tell()
                line = source.readline()
                if not line or not line.endswith(b'\n'):
                    self.state['offset'] = before
                    break
                try: row = json.loads(line)
                except (ValueError, UnicodeError):
                    self.state['parse_errors'] += 1
                    continue
                at = row.get('calculated_at', 0)
                if not self.run['started_at'] <= at <= self.run['ends_at']: continue
                if self.state['last_at'] is not None and at <= self.state['last_at']: continue
                snapshot = row['snapshot']
                quality = snapshot['quality']
                previous = self.state['last_at']
                if previous is not None:
                    gap = at-previous
                    self.state['max_gap_s'] = max(gap, self.state['max_gap_s'])
                    if gap <= self.run['max_age'] and quality == self.state['last_quality'] == 'valid':
                        self.state['valid_seconds'] += gap
                self.state['last_at'] = at
                self.state['last_quality'] = quality
                self.state['last_snapshot'] = snapshot
                self.state['samples'] += 1
                self.state['counts'][quality] = self.state['counts'].get(quality, 0)+1
                power = snapshot.get('power_kw')
                if power is not None: self.state['max_import_kw'] = max(self.state['max_import_kw'], power)
                # Real-mode coverage is separate from the counter watchdog:
                # normal counter increments reset that guard's episode.
                if power is None or power < .5 or previous is None or at-previous>self.run['max_age']:
                    self.state['import_run_since'] = at if power is not None and power>=.5 else None
                elif self.state.get('import_run_since') is None:
                    self.state['import_run_since'] = at
                if (self.state.get('import_run_since') is not None
                        and row['power']['at']-self.state['import_run_since']>=self.run['max_age']):
                    self.state['sustained_import_seen'] = True
                value = row.get('energy', {}).get('value')
                if value is not None:
                    if self.state['counter_first'] is None: self.state['counter_first'] = value
                    self.state['counter_last'] = value
                for record in row.get('records', []):
                    if (record['start'] >= self.run['first_full_quarter']
                            and record['end'] <= self.run['ends_at']):
                        self.state['records'][str(record['start'])] = record
                self.buffer.append(row)
                while self.buffer and self.buffer[0]['calculated_at'] < at-2700: self.buffer.popleft()
                if previous is not None and int(at//900) != int(previous//900): self.verify()

    def verify(self):
        report = check(list(self.buffer))
        if report['arithmetic_errors'] and not self.state['arithmetic_errors']:
            self.state['arithmetic_errors'] = report['arithmetic_errors'][:10]
        for interval in report['independently_verified_intervals']:
            if interval['start'] >= self.run['first_full_quarter']:
                self.state['verified'][str(interval['start'])] = interval

    def conditions(self, now, inspection):
        issues = {}
        if inspection.get('inspection_failed'):
            return {'docker_unreachable': 0}
        elif not inspection.get('state', {}).get('Running'):
            return {'test_instance_stopped': 0}
        started = inspection.get('state', {}).get('StartedAt')
        previous_start = self.state.get('container_started_at', self.run['container_started_at'])
        if started and started != previous_start:
            issues['test_instance_restarted'] = 0
        if started: self.state['container_started_at'] = started
        try:
            process_start = datetime.fromisoformat(started.replace('Z','+00:00')).timestamp()
        except (ValueError, AttributeError): process_start = self.run['started_at']
        warmup_until = math.ceil(process_start/900)*900
        grace_start = max(process_start, self.run['started_at'])
        last = self.state.get('last_at')
        if now-grace_start > self.run['max_age']+60 and (last is None or now-last > self.run['max_age']+60):
            issues['live_capture_stale'] = 0
        snapshot = self.state.get('last_snapshot') or {}
        confirmed_fault = False
        if self.run.get('entry_id'):
            try:
                engine=json.loads((self.test/'.storage'/('grid_peak_monitor.'+self.run['entry_id'])).read_text())['data']['engine']
                confirmed_fault=engine.get('counter_guard_version')==2 and engine.get('counter_stalled') is True
                if confirmed_fault: issues['confirmed_counter_stall'] = 0
            except (OSError,ValueError,KeyError): pass
        if last is not None and last >= warmup_until and snapshot.get('quality') != 'valid':
            if not (confirmed_fault and snapshot.get('quality')=='counter_stalled'):
                issues['quality_'+snapshot.get('quality', 'missing')] = 180 if snapshot.get('quality')=='waiting_report' else 90
        try:
            status = json.loads((self.test/'live-status.json').read_text())
            if now-grace_start>120 and status.get('state') not in ('active','test_reloading'):
                issues['live_mirror_'+str(status.get('state','missing'))] = 60
            if status.get('audit') == 'write_failed': issues['audit_write_failed'] = 0
        except (OSError, ValueError):
            if now-grace_start>180: issues['mirror_status_missing'] = 60
        if self.state['parse_errors']: issues['capture_corrupt_or_truncated'] = 0
        if self.state['arithmetic_errors']: issues['arithmetic_mismatch'] = 0
        # Allow two minutes for a boundary report before judging archive coverage.
        due_end = math.floor((now-120)/900)*900
        due = range(int(self.run['first_full_quarter']), int(due_end), 900)
        if any(str(at) not in self.state['records'] for at in due):
            issues['archive_quarter_missing'] = 0
        if any(r.get('quality') != 'valid' for r in self.state['records'].values()):
            issues['archive_quarter_invalid'] = 0
        try: changed=any(digest(self.project/name)!=expected for name,expected in self.run['code_hashes'].items())
        except OSError: changed=True
        if changed:
            issues['integration_changed_during_test'] = 0
        return issues

    def queue(self, notice_path):
        message = (
            'Automatischer lokaler Praxistest-Wächter, vom Nutzer beauftragt. '
            f'Lies zuerst die vertrauliche Meldung {notice_path} und {self.run_path}. '
            'Wenn die Meldung schon handled_at hat, keine erneute Nutzerbenachrichtigung. '
            'Prüfe die lokalen Nachweise und melde nur eine neue relevante Auffälligkeit '
            'oder das Abschlussergebnis. Im unveränderten Normalzustand still bleiben. '
            'Schreibe anschließend handled_at in die Meldungsdatei. '
            'Produktive HA NIE verändern, keine Produktions-Serviceaufrufe, nichts veröffentlichen. '
            'Die getestete Integration während des Laufs nicht ändern und Archivlücken nicht auffüllen. '
            'Nur die vorhandene Testinstanz grid-peak-monitor-preview darf bei technischen Ausfällen '
            'untersucht werden; ausdrückliche spätere Stop-Anweisungen des Nutzers beachten. '
            'Keinen neuen Agenten oder Goal anlegen. Beim Abschluss zeitliche Abdeckung, '
            'Rechenprüfung, reale Betriebsarten und verbleibende Grenzen nennen. '
            'Der Test darf nicht als bestanden gelten, wenn wesentliche Ausfälle oder Beweislücken vorliegen.'
        )
        try:
            result = subprocess.run([self.run['codex'], 'queue', '--thread', self.run['thread_id'],
                                     '--message', message], cwd=self.project,
                                    capture_output=True, text=True, timeout=30)
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired): return False

    def notify(self, kind, code, now, event):
        if event.get('queued_at'): return
        if now-event.get('attempted_at', 0) < 300: return
        notice = self.directory/'notices'/f"{kind}-{code}-{int(event['first_seen'])}.json"
        if not notice.exists():
            save(notice, {'kind':kind, 'code':code, 'first_seen':event['first_seen'],
                'observed_at':now, 'run_file':str(self.run_path), 'state_file':str(self.state_path),
                'report_file':str(self.directory/'result.json'), 'handled_at':None})
        event['attempted_at'] = now
        save(self.state_path,self.state)
        if self.notifier(notice): event['queued_at'] = now

    def reconcile(self, issues, now):
        for code in list(self.state['issues']):
            if code not in issues:
                event = self.state['issues'].pop(code)
                event.update(code=code, resolved_at=now)
                self.state['past_issues'].append(event)
        for code, delay in issues.items():
            event = self.state['issues'].setdefault(code, {'first_seen':now})
            if now-event['first_seen'] >= delay: self.notify('anomaly',code,now,event)

    def report(self, now):
        until = min(now, self.run['ends_at'])
        expected = max(0, int((until-self.run['first_full_quarter'])//900))
        records = self.state['records']
        valid = sum(r.get('quality')=='valid' for r in records.values())
        self.state['checked_at'] = now
        summary = {'run_started':local(self.run['started_at']), 'run_ends':local(self.run['ends_at']),
            'checked_at':local(now), 'elapsed_hours':(until-self.run['started_at'])/3600,
            'samples':self.state['samples'], 'quality_counts':self.state['counts'],
            'last_capture_at':local(self.state['last_at']) if self.state['last_at'] else None,
            'expected_complete_quarters':expected, 'valid_quarters':valid,
            'independently_verified_quarters':len(self.state['verified']),
            'invalid_quarters':len(records)-valid, 'missing_quarters':max(0,expected-len(records)),
            'arithmetic_errors':self.state['arithmetic_errors'], 'max_capture_gap_seconds':self.state['max_gap_s'],
            'valid_observed_hours':self.state['valid_seconds']/3600,
            'counter_first_kwh':self.state['counter_first'], 'counter_last_kwh':self.state['counter_last'],
            'maximum_import_kw':self.state['max_import_kw'],
            'sustained_import_observed':self.state['sustained_import_seen'],
            'active_issues':self.state['issues'], 'past_issues':self.state['past_issues'],
            'completed':now>=self.run['ends_at'], 'production_HA_modified':False,
            'limitation':'Observed source data and local estimates; assess real-mode coverage separately. No device control.'}
        save(self.directory/'result.json', summary)
        save(self.state_path, self.state)
        return summary

    def tick(self, now, inspection):
        self.consume()
        if now-self.last_check >= 300 or now>=self.run['ends_at']:
            self.verify(); self.last_check=now
        if now<=self.run['ends_at']:
            self.reconcile(self.conditions(now, inspection), now)
        if now>=self.run['started_at']+86400 and not self.state['midpoint_done']:
            summary = self.report(now)
            save(self.directory/'midpoint-24h.json', summary)
            self.state['midpoint_done'] = True  # Quiet when healthy; alerts are separate.
        if now>=self.run['ends_at']:
            self.state['completed'] = True
            self.report(now)
            event = self.state.setdefault('completion', {'first_seen':self.run['ends_at']})
            self.notify('complete','48h',now,event)
            self.state['completion_queued'] = bool(event.get('queued_at'))
        return self.report(now)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args()
    observer=Observer(args.run)
    with (observer.directory/'watch.lock').open('w') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit('This soak observer is already running')
        awake=None
        try:
            remaining=int(observer.run['ends_at']-time.time())
            if remaining>0 and not args.once:
                awake=subprocess.Popen(['/usr/bin/caffeinate','-is','-t',str(remaining)],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            while True:
                observer.tick(time.time(),inspect_test(observer.run['docker']))
                if args.once or observer.state.get('completion_queued'):break
                time.sleep(30)
        finally:
            if awake is not None and awake.poll() is None:
                awake.terminate();awake.wait(timeout=5)


if __name__=='__main__':main()

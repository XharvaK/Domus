"""D10 red-first contract tests; no Windows execution."""
import importlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock
from test_binding import load_probe, install_stubs

ROOT = Path(__file__).resolve().parents[1]


def command(name='status', args=None, **changes):
    row = dict(v=1, id='a'*32, issued_at_ms=1000, expires_at_ms=61000,
               issuer='agent:coder', command=name, args={} if args is None else args)
    row.update(changes)
    return row


class ParserTests(unittest.TestCase):
    def setUp(self):
        load_probe()
        self.assertTrue((ROOT/'src/ashley_e1/cmdbox.py').exists(), 'cmdbox missing')
        self.box = importlib.import_module('ashley_e1.cmdbox')

    def parse(self, row, now=1000, used=()):
        return self.box.parse(json.dumps(row).encode(), now, used)

    def test_vocabulary_shapes_and_reply(self):
        shapes = {'arm': {'name':'lab_e1'}, 'prepare': {'object_id':'123'},
                  'sit_trial': {'object_id':'123'}, 'sit': {'token':'a'*16}}
        for name in 'arm start stop disarm prepare sit pause release status sit_trial'.split():
            with self.subTest(name=name):
                row = command(name, shapes.get(name, {}))
                self.assertEqual(self.parse(row), (row, None))
                self.assertEqual(self.parse(command(name, {'extra':1}))[1], 'BAD_ARGS')
        self.assertEqual(self.parse(command('arm', {'name':'lab_e1_fork'}))[1], None)
        self.assertEqual(json.loads(self.box.reply('a'*32,'OK',None,{'ok':True})),
                         dict(id='a'*32,status='OK',code=None,result={'ok':True}))

    def test_every_rejection_code(self):
        cases = [('BAD_SHAPE', []), ('BAD_SHAPE', command(extra=1)),
                 ('BAD_VERSION',command(v=True)), ('BAD_ID',command(id='A'*32)),
                 ('EXPIRED',command(expires_at_ms=999)),
                 ('NOT_YET_VALID',command(issued_at_ms=1001)),
                 ('TTL_TOO_LONG',command(expires_at_ms=61001)),
                 ('BAD_SHAPE',command(issued_at_ms=True)),
                 ('BAD_ISSUER',command(issuer='agent:A')),
                 ('UNKNOWN_COMMAND',command(command='eval')),
                 ('BAD_ARGS',command('prepare',{'object_id':'1'*21})),
                 ('BAD_ARGS',command('sit',{'token':'A'*16}))]
        for code,row in cases:
            with self.subTest(code=code,row=row): self.assertEqual(self.parse(row)[1],code)
        self.assertEqual(self.box.parse(b'x'*4097,1000,())[1],'TOO_LARGE')
        for raw in (b'{',b'\xff',b'{"v":1,"v":1}'):
            self.assertEqual(self.box.parse(raw,1000,())[1],'BAD_JSON')
        self.assertEqual(self.parse(command(),used={'a'*32})[1],'REPLAYED')

    def test_ttl_boundaries(self):
        for ttl in (0,60000):
            row=command(expires_at_ms=1000+ttl)
            self.assertEqual(self.parse(row,1000)[1],None)
            self.assertEqual(self.parse(row,1000+ttl)[1],None)
        self.assertEqual(self.parse(command(expires_at_ms=61001))[1],'TTL_TOO_LONG')


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.package,self.probe,_=load_probe()
        self.s=self.package.schema

    def test_v4_and_closed_command_event(self):
        s=self.s
        self.assertEqual((s.OBSERVATION_SCHEMA_VERSION,s.TELEMETRY_SCHEMA_ID),(4,'e1.telemetry/v4'))
        payload=dict(id='a'*32,issuer='agent:coder',command='status',status='OK',code=None)
        def row(p): return s.make_record('command_event',telemetry_session_id='u',
                                        wall_timestamp_ms=1,monotonic_ns=1,e2=p)
        s.validate_record(row(payload))
        for key,value in [('id','A'*32),('issuer','agent:A'),('command','eval'),
                          ('status','MAYBE'),('code','x'*65),('code',1)]:
            with self.subTest(key=key):
                with self.assertRaises(s.SchemaError): s.validate_record(row(dict(payload,**{key:value})))
        for status in ('OK','ERROR','REJECTED'):
            s.validate_record(row(dict(payload,status=status)))

    def test_h4(self):
        rows=[]
        c=self.probe._E2
        c._emit_row=rows.append
        for reason,phase in [('STOP','RELEASED_ON_STOP'),('DISARM','RELEASED_ON_DISARM')]:
            c.pause_request=object()
            with mock.patch.object(c,'_remove_request',return_value=True): c._release_pause(reason)
            self.assertEqual(rows[-1]['e2']['phase'],phase)


class ConsoleTests(unittest.TestCase):
    def test_cheat_output_only(self):
        load_probe()
        calls=install_stubs()
        commands=sys.modules['sims4.commands']
        cheat=[]
        commands.cheat_output=lambda text,connection: cheat.append((text,connection))
        commands.output=lambda text,connection: calls['outputs'].append((text,connection))
        probe=importlib.reload(sys.modules['ashley_e1.probe'])
        probe._output('visible',123)
        self.assertEqual(cheat,[('visible',123)])
        self.assertEqual(calls['outputs'],[])


class InboxTests(unittest.TestCase):
    def setUp(self):
        _,self.p,self.calls=load_probe()
        self.assertTrue(hasattr(self.p,'_inbox_tick'),'inbox pump missing')
        self.root=Path(self.p._TELEMETRY_ROOT)/'cmd'
        self.assertTrue(self.p._dispatch_inbox(_session_id=9))

    def put(self, row, name='001.json'):
        (self.root/'inbox'/name).write_bytes(json.dumps(row).encode())

    def tick(self):
        with mock.patch.object(self.p.time,'time',return_value=1): self.p._inbox_tick()

    def reply(self, id='a'*32): return json.loads((self.root/'outbox'/(id+'.json')).read_bytes())

    def test_unarmed_status_inert_and_bootstrap(self):
        self.assertTrue(self.p._dispatch_inbox(_session_id=9))
        self.assertEqual(len(self.calls['alarms']),1)
        settings=self.calls['alarms'][0][2]
        self.assertEqual((settings['repeating'],settings['cross_zone'],settings['time_span']),(True,False,1))
        before=list(self.root.rglob('*'))
        with mock.patch.object(self.p.os,'listdir',wraps=os.listdir) as ls:
            self.tick()
            self.assertEqual(ls.call_count,1)
        self.assertEqual(list(self.root.rglob('*')),before)
        self.put(command()); self.tick()
        reply=self.reply()
        self.assertEqual(reply['status'],'OK')
        result=reply['result']
        self.assertEqual((result['state'],result['inbox'],result['probe_version'],result['schema_version']),('UNARMED','on','2.3.2',4))
        for key in ('armed_name','signatures','continuation','lineage_class','designated_sim_id','verdicts'): self.assertIn(key,result)
        self.assertIsNone(self.p._WRITER)
        self.assertTrue((self.root/'done'/('a'*32+'.json')).exists())

    def test_dispatch_telemetry_replay_and_survives_stop(self):
        self.put(command('arm',{'name':'lab_e1'})); self.tick()
        self.assertEqual(self.reply()['result'],{'ok':True,'lines':[]})
        rows=self.p._WRITER.rows
        self.assertEqual(rows[-1]['event_kind'],'command_event')
        self.p.schema.validate_record(rows[-1])
        handle=self.p._INBOX_HANDLE
        self.assertTrue(self.p._dispatch_start())
        self.assertTrue(self.p._dispatch_stop())
        self.assertTrue(self.p._dispatch_disarm())
        self.assertIs(self.p._INBOX_HANDLE,handle)
        self.p._INBOX_USED_IDS.clear()
        self.put(command(),'002.json'); self.tick()
        self.assertEqual(self.reply()['code'],'REPLAYED')

    def test_four_files_and_malformed_no_dispatch(self):
        for i in range(5): self.put(command(id='%032x'%i), '%03d.json'%i)
        self.tick()
        self.assertEqual(len(list((self.root/'outbox').glob('*.json'))),4)
        self.assertEqual([p.name for p in (self.root/'inbox').glob('*.json')],['004.json'])
        self.tick()
        self.put(command(command='eval'),'bad.json')
        with mock.patch.object(self.p,'_dispatch_arm') as dispatch:
            self.tick(); dispatch.assert_not_called()
        self.assertEqual((self.reply()['status'],self.reply()['code']),('REJECTED','UNKNOWN_COMMAND'))

    def test_disarm_event_with_active_writer(self):
        self.put(command('arm', {'name':'lab_e1'})); self.tick()
        self.put(command('disarm', id='b'*32), '002.json'); self.tick()
        self.assertEqual(self.reply('b'*32)['status'], 'OK')
        self.assertEqual(self.p._STATE, 'UNARMED')
        self.assertEqual(self.p._WRITER.rows[-1]['event_kind'], 'command_event')
        self.assertEqual(self.p._WRITER.rows[-1]['e2']['command'], 'disarm')

    def test_invalid_json_rejected_without_dispatch(self):
        (self.root/'inbox'/'broken.json').write_bytes(b'{')
        with mock.patch.object(self.p, '_inbox_dispatch') as dispatch:
            self.tick()
            dispatch.assert_not_called()
        replies=list((self.root/'outbox').glob('*.json'))
        self.assertEqual(len(replies), 1)
        reply=json.loads(replies[0].read_bytes())
        self.assertEqual((reply['status'], reply['code']), ('REJECTED', 'BAD_JSON'))
        self.assertTrue((self.root/'done'/replies[0].name).exists())

    def test_dispatch_error_reply(self):
        self.put(command('start'))
        with mock.patch.object(self.p, '_dispatch_start', side_effect=RuntimeError('failure')):
            self.tick()
        self.assertEqual(self.reply()['status'], 'ERROR')
        self.assertEqual(self.reply()['code'], 'RuntimeError')
        self.assertEqual(self.reply()['result'], {'ok':False, 'lines':[]})

    def test_claim_atomic_reply_then_done(self):
        self.put(command())
        with mock.patch.object(self.p.os, 'replace', wraps=os.replace) as replace:
            self.tick()
        moves=[(Path(c[0][0]), Path(c[0][1])) for c in replace.call_args_list]
        self.assertEqual(moves, [
            (self.root/'inbox/001.json', self.root/'inbox/001.json.taken'),
            (self.root/'outbox'/('a'*32+'.json.tmp'), self.root/'outbox'/('a'*32+'.json')),
            (self.root/'inbox/001.json.taken', self.root/'done'/('a'*32+'.json'))])
        self.assertEqual(set(self.reply()), {'id','status','code','result','issuer'})

    def test_a12_reply_issuer_attribution(self):
        self.put(command())
        self.tick()
        self.assertEqual(self.reply().get('issuer'), 'agent:coder')

    def test_verdict_history(self):
        self.p._cmd_arm('LAB_E1')
        for i in range(7):
            self.p._emit(self.p.schema.make_record('experiment_event',telemetry_session_id='u',wall_timestamp_ms=1,monotonic_ns=1,
                e2=dict(phase='VERDICT',code='PASS',experiment_id=str(i),object_id=None,token=None,interaction_id=None,claims=None,finishing_type=None,detail='d')))
        self.put(command()); self.tick()
        self.assertEqual([v['experiment_id'] for v in self.reply()['result']['verdicts']],list(map(str,range(2,7))))


class PowerShellStaticTests(unittest.TestCase):
    def test_source_not_lf_recursive_before_compile(self):
        text=(ROOT/'tools/build.ps1').read_text(encoding='utf-8')
        self.assertIn('SOURCE_NOT_LF',text)
        self.assertIn('Get-ChildItem -LiteralPath $sourceRoot -Recurse -Filter *.py -File',text)
        self.assertIn('[System.IO.File]::ReadAllBytes',text)
        self.assertIn('-contains 13',text)
        self.assertLess(text.index('SOURCE_NOT_LF'),text.index('$compileCode'))

    def test_zipimport_flags(self):
        text=(ROOT/'tools/verify.ps1').read_text(encoding='utf-8')
        self.assertIn("int.from_bytes(archive.read(name)[4:8], 'little') != 1",text)

    def test_cleanup_precedes_pass(self):
        text=(ROOT/'tools/verify.ps1').read_text(encoding='utf-8')
        self.assertGreater(text.index('Record-Pass ("REPRODUCIBLE BUILD_SHA256='),text.index('REPRODUCIBLE temp cleanup:'))
        self.assertIn('if ($reproSucceeded -and -not $failed)',text)

    def test_optional_nested_host(self):
        text=(ROOT/'tools/verify.ps1').read_text(encoding='utf-8')
        self.assertIn('$verifyArgs += @("-HostPythonPath", $HostPythonPath)',text)
        self.assertIn('& $powershellPath @verifyArgs',text)
        guard='if (-not [string]::IsNullOrWhiteSpace($HostPythonPath)) {'
        nested=text[text.index('$verifyArgs ='):text.index('$verifyOutput = & $powershellPath @verifyArgs')]
        self.assertIn(guard,nested)
        self.assertLess(nested.index(guard),nested.index('$verifyArgs +='))

class RemainingContractsTests(unittest.TestCase):
    def test_version_and_exact_a12(self):
        for path in ('src/ashley_e1/__init__.py','src/ashley_e1/schema.py',
                     'tools/build.ps1','tools/verify.ps1','README.md'):
            self.assertIn('2.3.2',(ROOT/path).read_text(encoding='utf-8'),path)
        for path in ('tools/install.ps1','tools/remove.ps1'):
            self.assertIn('2.3.1',(ROOT/path).read_text(encoding='utf-8'),path)
        expected="| A12 | §4 harness inputs are the Owner's console commands; §5 telemetry schema v2 | Probe 2.2.0, telemetry schema v3: a local command inbox (`AshleyE1Telemetry/cmd/inbox`, single-use ids, ≤ 60 s expiry, closed vocabulary and argument shapes) is a harness input path equivalent to the console. Commands run through the same dispatchers; actions keep the `EXPERIMENT` origin; the issuer (`agent:<name>`, `helper`, `console`) is recorded in a `command_event` row and the reply file as attribution: an agent acts on the Owner's behalf. `sit_trial` is prepare then sit inside one call, with admission unchanged. Nothing in the inbox can do what the console cannot. Schema v3 also adds `RELEASED_ON_STOP`. Console replies use `cheat_output`, because `sims4.commands.output` is a no-op in release builds. The pump starts when a zone reaches RUNNING, registered through the zone manager's object-add callback without injection, or by the console command `ashley_e1.inbox`. | Plan Phase 2 (agent-run LAB, no 30 s human token race); R-H2 (vanilla `commands.py` bytecode: `output` has an empty body); D9b (H4 deferred to one schema bump). |"
        plan=(ROOT.parent/'docs/PROJECT_ASHLEY_SIMS4_EMBODIMENT_E2_IMPLEMENTATION_READY_PLAN_V1.md').read_text(encoding='utf-8').splitlines()
        index=next(i for i,line in enumerate(plan) if line.startswith('| A11 |'))
        self.assertEqual(plan[index+1],expected)
        a13=next(line for line in plan if line.startswith('| A13 |'))
        self.assertIn('Probe 2.3.x, telemetry schema v4',a13)
        self.assertIn('`presence`',a13)

    def test_module_lists_and_no_reflection(self):
        sys.path.insert(0,str(ROOT/'tools'))
        import check_guards
        self.assertIn('cmdbox',check_guards.PRODUCTION_MODULES)
        self.assertIn('cmdbox.py',check_guards.PURE_FILES)
        self.assertIn('"cmdbox"',(ROOT/'tools/build.ps1').read_text(encoding='utf-8'))
        for path in (ROOT/'src').rglob('*.py'):
            self.assertEqual(check_guards.scan_text(path.read_text(encoding='utf-8'),str(path)),[])

    def test_sit_trial_real_admission_and_experiment_origin(self):
        from test_e2 import ControlFlowTests, CHAIR
        fixture=ControlFlowTests(); fixture.setUp()
        p=fixture.probe
        self.assertTrue(hasattr(p,'_inbox_tick'),'inbox pump missing')
        fixture.arm_start_poll(fixture.continuing())
        fixture.learn_signature()
        p._dispatch_inbox()
        row=command('sit_trial',{'object_id':CHAIR})
        inbox=Path(p._TELEMETRY_ROOT)/'cmd/inbox'
        (inbox/'trial.json').write_bytes(json.dumps(row).encode())
        with mock.patch.object(p.time,'time',return_value=1): p._inbox_tick()
        reply=json.loads((inbox.parent/'outbox'/('a'*32+'.json')).read_bytes())
        self.assertEqual(reply['status'],'OK')
        self.assertTrue(reply['result']['lines'][0].startswith('PREPARE_OK token '))
        self.assertTrue(any('PUSHED' in line for line in reply['result']['lines']))
        self.assertEqual(len(fixture.pushes),1)
        self.assertEqual(fixture.pushes[0][2].source,'SCRIPT_WITH_USER_INTENT')
        self.assertEqual(len(p._E2.experiments),1)
        # EXPERIMENT is the plan's authority classification, not an Experiment field.
        self.assertEqual(p._E2.open_ids, {'777'})
        self.assertEqual(fixture.e2('experiment_event')[-1]['phase'],'PUSHED')

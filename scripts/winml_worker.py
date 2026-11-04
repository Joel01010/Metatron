from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path


def _initialize():
    # Microsoft documents this workaround for the Python framework-dependent
    # Windows ML package because winrt-runtime may ship msvcp140.dll.
    try:
        from importlib import metadata
        site = Path(str(metadata.distribution('winrt-runtime').locate_file('')))
        dll = site / 'winrt' / 'msvcp140.dll'
        if dll.exists():
            dll.unlink()
    except Exception:
        pass
    from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import InitializeOptions, initialize
    import winui3.microsoft.windows.ai.machinelearning as winml
    import onnxruntime as ort
    handle = initialize(options=InitializeOptions.ON_NO_MATCH_SHOW_UI)
    handle.__enter__()
    return handle, winml, ort


def _version(pkg):
    if pkg is None:
        return None
    try:
        v = pkg.version
        return f"{v.major}.{v.minor}.{v.build}.{v.revision}"
    except Exception:
        return None


def _kind(d):
    hw = getattr(d, 'hardware_device', None)
    return str(getattr(getattr(hw, 'type', None), 'name', getattr(hw, 'type', ''))).upper()


def _devices(ort):
    out = []
    fn = getattr(ort, 'get_ep_devices', None)
    if not callable(fn):
        return out
    for i, d in enumerate(fn()):
        hw = getattr(d, 'hardware_device', None)
        out.append({
            'index': i,
            'ep_name': str(getattr(d, 'ep_name', '')),
            'kind': _kind(d),
            'name': str(getattr(hw, 'name', '') or ''),
            'vendor': str(getattr(hw, 'vendor', '') or ''),
            'device_id': str(getattr(hw, 'device_id', '') or ''),
        })
    return out


def _register_ready(winml, ort, names=None):
    """Ensure + register EPs in THIS process.

    Registration is process-local. Session creation/probing therefore calls
    this helper before get_ep_devices()/InferenceSession in the same worker.
    """
    wanted = set(names) if names else None
    cat = winml.ExecutionProviderCatalog.get_default()
    results = []
    for p in cat.find_all_providers():
        name = str(p.name)
        if wanted is not None and name not in wanted:
            continue
        before = str(getattr(getattr(p, 'ready_state', None), 'name', getattr(p, 'ready_state', '')))
        ok = False
        err = ''
        status = ''
        try:
            result = p.ensure_ready_async().get()
            status = str(getattr(getattr(result, 'status', None), 'name', getattr(result, 'status', '')))
            library = str(getattr(p, 'library_path', '') or '')
            if library:
                ort.register_execution_provider_library(name, library)
            ready = str(getattr(getattr(p, 'ready_state', None), 'name', getattr(p, 'ready_state', '')))
            ok = 'SUCCESS' in status.upper() or 'READY' in ready.upper()
        except Exception as e:
            err = f'{type(e).__name__}: {e}'
        results.append({
            'name': name,
            'before': before,
            'status': status,
            'ready': ok,
            'error': err,
            'library_path': str(getattr(p, 'library_path', '') or ''),
        })
    return results


def catalog(winml, ort):
    cat = winml.ExecutionProviderCatalog.get_default()
    providers = []
    for p in cat.find_all_providers():
        providers.append({
            'name': str(p.name),
            'ready_state': str(getattr(getattr(p, 'ready_state', None), 'name', getattr(p, 'ready_state', ''))),
            'version': _version(getattr(p, 'package_id', None)),
            'library_path': str(getattr(p, 'library_path', '') or ''),
        })
    # Catalog inventory intentionally does not imply routability. Devices here
    # may be empty until provider registration happens in this process.
    return {'providers': providers, 'devices': _devices(ort)}


def ensure(winml, ort, names=None):
    results = _register_ready(winml, ort, names)
    return {'results': results, 'devices': _devices(ort), 'registration_scope': 'current_process'}


def _synthetic_inputs(session):
    import numpy as np
    feeds = {}
    for inp in session.get_inputs():
        shape = []
        for dim in inp.shape:
            if isinstance(dim, int) and dim > 0:
                shape.append(dim)
            else:
                # A conservative one-element dynamic dimension. This is enough
                # for many verification models; unsupported models report a
                # warm-up failure rather than claiming placement.
                shape.append(1)
        t = str(inp.type).lower()
        if 'float16' in t:
            dtype = np.float16
        elif 'float' in t or 'double' in t:
            dtype = np.float32
        elif 'int64' in t:
            dtype = np.int64
        elif 'int32' in t:
            dtype = np.int32
        elif 'bool' in t:
            dtype = np.bool_
        else:
            raise RuntimeError(f'unsupported synthetic input type {inp.type!r} for {inp.name}')
        feeds[inp.name] = np.zeros(shape, dtype=dtype)
    return feeds


def probe(winml, ort, model: str, kinds=None, names=None, cache_dir=''):
    model_path = Path(model)
    if not model_path.is_file():
        raise FileNotFoundError(model)
    registrations = _register_ready(winml, ort, names)
    devices = list(getattr(ort, 'get_ep_devices', lambda: [])())
    wanted_kinds = [str(x).upper() for x in (kinds or ['NPU', 'GPU', 'CPU'])]
    errors = []
    for kind in wanted_kinds:
        for d in devices:
            if _kind(d) != kind:
                continue
            ep = str(getattr(d, 'ep_name', '') or '')
            hw = getattr(d, 'hardware_device', None)
            name = str(getattr(hw, 'name', '') or d)
            try:
                opts = ort.SessionOptions()
                add_cfg = getattr(opts, 'add_session_config_entry', None)
                if kind in {'NPU', 'GPU'} and callable(add_cfg):
                    add_cfg('session.disable_cpu_ep_fallback', '1')
                add = getattr(opts, 'add_provider_for_devices', None)
                if not callable(add):
                    raise RuntimeError('add_provider_for_devices unavailable')
                provider_options = {}
                if cache_dir and ep == 'OpenVINOExecutionProvider':
                    provider_options['cache_dir'] = cache_dir
                add([d], provider_options)
                session = ort.InferenceSession(str(model_path), sess_options=opts)
                feeds = _synthetic_inputs(session)
                session.run(None, feeds)
                return {
                    'verified': True,
                    'kind': kind,
                    'provider': ep,
                    'device': name,
                    'model': str(model_path),
                    'providers': list(session.get_providers()),
                    'registration_scope': 'same_process_as_session',
                    'registrations': registrations,
                    'devices': _devices(ort),
                }
            except Exception as exc:
                errors.append(f'{kind}/{ep}/{name}: {type(exc).__name__}: {exc}')
    raise RuntimeError('all accelerator probes failed: ' + ' | '.join(errors[-12:]))


def handle(req, winml, ort):
    cmd = str(req.get('cmd') or '')
    p = req.get('params') or {}
    if cmd == 'catalog':
        return catalog(winml, ort)
    if cmd == 'ensure':
        return ensure(winml, ort, p.get('names'))
    if cmd == 'devices':
        # Register first so the returned list represents routable devices in
        # this worker rather than bare hardware/catalog discovery.
        regs = _register_ready(winml, ort, p.get('names'))
        return {'devices': _devices(ort), 'registrations': regs, 'registration_scope': 'current_process'}
    if cmd == 'probe':
        return probe(winml, ort, p['model'], p.get('kinds'), p.get('names'), p.get('cache_dir', ''))
    raise ValueError(f'unknown cmd {cmd!r}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--once', choices=['catalog', 'ensure', 'devices', 'probe'])
    ap.add_argument('--names', default='')
    ap.add_argument('--model', default='')
    ap.add_argument('--kinds', default='NPU,GPU,CPU')
    ap.add_argument('--cache-dir', default='')
    a = ap.parse_args()
    handle_ctx, winml, ort = _initialize()
    try:
        if a.once:
            params = {}
            if a.names:
                params['names'] = [x for x in a.names.split(',') if x]
            if a.model:
                params['model'] = a.model
            if a.kinds:
                params['kinds'] = [x for x in a.kinds.split(',') if x]
            if a.cache_dir:
                params['cache_dir'] = a.cache_dir
            print(json.dumps(handle({'cmd': a.once, 'params': params}, winml, ort), separators=(',', ':')))
            return
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            rid = None
            try:
                req = json.loads(line)
                rid = req.get('id')
                result = handle(req, winml, ort)
                out = {'id': rid, 'ok': True, 'result': result}
            except Exception as e:
                out = {'id': rid, 'ok': False, 'error': {'message': str(e), 'type': type(e).__name__}}
            print(json.dumps(out, separators=(',', ':')), flush=True)
    finally:
        handle_ctx.__exit__(None, None, None)


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(json.dumps({'ok': False, 'error': {'message': str(e), 'trace': traceback.format_exc(limit=3)}}))
        raise

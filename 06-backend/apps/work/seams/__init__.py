"""work → other-module SEAMS — one READ-ONLY file per module (BR-WRK-002).

Every cross-module read this module makes goes through one of these files and
nowhere else; a model of another app is imported ONLY inside this package
(G78 fails an import of `apps.<other>.models` or `apps.metering.connections`
anywhere else under `apps/work/`). Each file resolves the owning module at
call time — `resolve(module, attribute)`, the shape `apps/metering/seams.py`
established — and filters every read by the tenant in context, so a read with
no `app.tenant_id` answers nothing (US-WRK-005 TC-7).

Naming rule, asserted by US-WRK-005 TC-6: no public name here starts with
`create_`, `set_`, `update_`, `delete_` or `post_`. The ONE door that causes a
write — `metering_seam.raise_work_order` — is metering's own service called by
name, never an ORM write, and its docstring says so.
"""

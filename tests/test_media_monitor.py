import asyncio

from letrasbr_api.media_monitor import WindowsMediaMonitor


def test_cover_is_emitted_only_when_it_changes():
    monitor = WindowsMediaMonitor()
    emitted = []
    monitor.cover_changed.connect(emitted.append)
    covers = iter([b"old", b"old", b"new", b"new"])

    async def fake_read(props):
        return next(covers)

    monitor._read_thumbnail = fake_read
    for _ in range(4):  # troca de faixa lê a capa antiga; a nova chega depois
        asyncio.run(monitor._check_cover(None))
    assert emitted == [b"old", b"new"]

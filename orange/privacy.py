"""Privacy helpers: status lines so you always know when the mic is on."""


def wake_on():
    print("🟠 Mic on: waiting for wake word (audio not saved or sent)")


def mic_on():
    print("🔴 Listening")


def mic_off():
    print("⚪ Mic off")

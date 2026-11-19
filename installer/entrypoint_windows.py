"""Windows PyInstaller GUI entrypoint with non-interactive smoke test."""
import sys


def main():
    if '--self-test' in sys.argv:
        from deckforge import __version__
        from deckforge.project import default_config
        from deckforge.manufacturing import default_template
        from deckforge.vision import expected_suit_count
        assert len(default_config()['cards'])==78
        assert default_template()['template_received_from_manufacturer'] is False
        assert expected_suit_count('P09')[1]==9
        print('DeckForge',__version__,'Windows frozen smoke test OK')
        return
    from deckforge.studio import launch
    launch(None)

if __name__=='__main__':
    main()

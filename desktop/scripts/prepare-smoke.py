"""Prepare disposable test data outside the installer for native packaged-app acceptance."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from engine.desktop.workspace import Config, Workspace
from engine.models import now
from engine.tests.case_builder_fixtures import complete_case, store_with_synthetic_files


def prepare(output: Path, codedb: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    data = output / 'workspace données 100% #'
    if data.exists():
        raise SystemExit('Use a new smoke output directory. Existing app data is never overwritten.')
    source = output / 'chosen code database 100% #.sqlite'
    shutil.copyfile(codedb, source)
    os.environ['BATATIS_CODEDB'] = str(source)
    workspace = Workspace(Config('dev', data / 'workspaces' / 'dev' / 'cases.sqlite', source))
    applicant = workspace.profiles['applicant'].user_id
    case = complete_case()
    case.title = 'SYNTHETIC native review fixture'
    case.owner_id, case.authority = applicant, 'edmonton'
    case = store_with_synthetic_files(workspace.store, case)

    image = Image.frombytes('RGB', (500, 500), hashlib.shake_256(b'batatis-synthetic-native-pdf').digest(750_000))
    pdf = io.BytesIO()
    page = Canvas(pdf, pageCompression=0, invariant=1)
    page.drawString(40, 800, 'SYNTHETIC native attachment. No design or professional evidence.')
    page.drawImage(ImageReader(image), 40, 250, width=500, height=500)
    page.save()
    content = pdf.getvalue()
    (output / 'plan données 100% #.pdf').write_bytes(content)
    scenario = {
        'userData': str(data), 'codeDb': str(source), 'reviewCase': case.id,
        'applicantId': applicant, 'pdfSha256': hashlib.sha256(content).hexdigest(),
        'pdfFile': 'plan données 100% #.pdf', 'createdAt': now(),
    }
    (output / 'scenario.json').write_text(json.dumps(scenario, indent=2), encoding='utf-8')


if __name__ == '__main__':
    prepare(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())

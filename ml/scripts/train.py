"""Train the production SignTransformer on collected NSL data. Requires the ``full`` extra.

This is the real Phase 1 model (TECH_STACK.md Layer 2). It needs collected NSL takes and a
GPU/Colab, and Python 3.11/3.12 (torch has no 3.14 wheels yet). Until real data exists,
use ``train_lite.py`` for the runnable interim model.

    python scripts/train.py --epochs 60 --batch-size 64

Pretraining note (PROJECT_PLAN.md Phase 1): pretrain on WLASL skeleton features first, then
fine-tune here. Add a --init-weights flag to load a pretrained checkpoint.

Evaluation is on **held-out signers** (split_by_signer). Target: >=85% top-1.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from signbridge.config import ML_ROOT
from signbridge.preprocessing import discover, split_by_signer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--out", type=Path, default=ML_ROOT / "artifacts" / "sign_transformer.pt")
    ap.add_argument("--init-weights", type=Path, default=None, help="pretrained checkpoint (WLASL)")
    args = ap.parse_args()

    import torch
    from torch.utils.data import DataLoader

    from signbridge.dataset import LandmarkDataset, build_label_set
    from signbridge.models.sign_transformer import SignTransformer, export_onnx

    samples = discover()
    if not samples:
        raise SystemExit("No data in data/raw. Collect signs (capture_tool.py) or run synth_data.py.")
    split = split_by_signer(samples, seed=1)
    labels = build_label_set(samples)

    train_ds = LandmarkDataset(split.train, labels, train=True)
    val_ds = LandmarkDataset(split.val, labels)
    train_dl = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)
    val_dl = DataLoader(val_ds, batch_size=args.batch_size)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SignTransformer(num_classes=len(labels)).to(device)
    if args.init_weights:
        model.load_state_dict(torch.load(args.init_weights, map_location=device), strict=False)
    print(f"model params: {model.num_parameters() / 1e6:.1f}M | classes: {len(labels)} | device: {device}")

    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    loss_fn = torch.nn.CrossEntropyLoss()
    best = 0.0

    for epoch in range(1, args.epochs + 1):
        model.train()
        for x, y in train_dl:
            x, y = x.to(device), y.to(device)
            opt.zero_grad()
            loss_fn(model(x), y).backward()
            opt.step()

        model.eval()
        correct = total = 0
        with torch.no_grad():
            for x, y in val_dl:
                x, y = x.to(device), y.to(device)
                correct += (model(x).argmax(1) == y).sum().item()
                total += y.numel()
        acc = correct / max(total, 1)
        print(f"epoch {epoch:3d}  val_acc(heldout signers)={acc:.1%}")
        if acc > best:
            best = acc
            args.out.parent.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), args.out)

    print(f"best held-out-signer accuracy: {best:.1%}  [Phase 1 target >=85%]")
    export_onnx(model, str(args.out.with_suffix(".onnx")))
    print(f"saved {args.out} and ONNX export")


if __name__ == "__main__":
    main()

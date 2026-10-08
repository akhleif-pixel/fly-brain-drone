# Brain

Laptop side: the fly brain model and the control loop.

## Phase 1: get the model running

Quick look: open https://github.com/philshiu/Drosophila_brain_model and click **Open in Colab**.

Local install (Anaconda Prompt, from this `brain/` folder):

```
git clone https://github.com/philshiu/Drosophila_brain_model.git
cd Drosophila_brain_model
conda env create -f environment.yml
conda activate <name from the first line of environment.yml>
jupyter notebook example.ipynb
```

Milestone: activating the sugar-sensing neurons makes MN9 fire.

`Drosophila_brain_model/` is cloned here but not committed (see `.gitignore`).

## Phase 2: webcam eyes

OpenCV looming detector → stimulate LPLC2/LC4 → read the Giant Fiber. Neuron IDs come from FlyWire Codex (codex.flywire.ai).

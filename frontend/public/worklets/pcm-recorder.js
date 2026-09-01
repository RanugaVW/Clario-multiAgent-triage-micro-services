/**
 * AudioWorklet that turns the live microphone graph into the exact wire format
 * the voice-to-text service expects: mono, 16 kHz, little-endian int16.
 *
 * The AudioContext is normally created at 16 kHz already, but browsers are
 * allowed to ignore that hint, so this processor resamples with linear
 * interpolation whenever `sampleRate` differs from the target.
 */
class PCMRecorderProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const opts = (options && options.processorOptions) || {};
    const targetSampleRate = opts.targetSampleRate || 16000;
    // `frameSize` output samples per message: 2048 @ 16 kHz ~= 128 ms.
    const frameSize = opts.frameSize || 2048;

    this.ratio = sampleRate / targetSampleRate;
    this.pending = new Float32Array(0);
    this.readPos = 0;
    this.out = new Int16Array(frameSize);
    this.outLen = 0;
    this.stopped = false;

    this.port.onmessage = (event) => {
      if (event.data === 'flush') this.flush();
      else if (event.data === 'stop') {
        this.flush();
        this.stopped = true;
      }
    };
  }

  flush() {
    if (this.outLen === 0) return;
    const frame = this.out.slice(0, this.outLen);
    this.outLen = 0;
    this.port.postMessage(frame.buffer, [frame.buffer]);
  }

  pushSample(value) {
    const clamped = Math.max(-1, Math.min(1, value));
    this.out[this.outLen++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    if (this.outLen === this.out.length) this.flush();
  }

  process(inputs) {
    if (this.stopped) return false;

    const channel = inputs[0] && inputs[0][0];
    if (!channel || channel.length === 0) return true;

    const merged = new Float32Array(this.pending.length + channel.length);
    merged.set(this.pending);
    merged.set(channel, this.pending.length);
    this.pending = merged;

    let pos = this.readPos;
    while (Math.floor(pos) + 1 < this.pending.length) {
      const index = Math.floor(pos);
      const frac = pos - index;
      this.pushSample(
        this.pending[index] * (1 - frac) + this.pending[index + 1] * frac
      );
      pos += this.ratio;
    }

    // Keep the sample the next interpolation still needs to read from.
    const consumed = Math.floor(pos);
    if (consumed > 0) {
      this.pending = this.pending.slice(consumed);
      pos -= consumed;
    }
    this.readPos = pos;
    return true;
  }
}

registerProcessor('pcm-recorder', PCMRecorderProcessor);

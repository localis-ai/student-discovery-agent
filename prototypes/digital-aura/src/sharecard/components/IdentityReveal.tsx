import { motion, useTransform, type MotionValue } from 'motion/react';
import { useContext, useMemo, useRef } from 'react';
import { scrambleGlyph } from '../animation/timeline';
import type { RatioLayout } from '../layout';
import type { ShareCardData } from '../types';
import { TitleStyleContext, trackProps, useFitText, useOverlayMotion } from './overlay-motion';
import { StrengthChips } from './StrengthChips';

interface IdentityRevealProps {
  data: ShareCardData;
  layout: RatioLayout;
  time: MotionValue<number>;
}

const CONTENT_WIDTH = 344;

const graphemes = (text: string) =>
  typeof Intl.Segmenter === 'function'
    ? Array.from(
        new Intl.Segmenter('vi', { granularity: 'grapheme' }).segment(text),
        (s) => s.segment,
      )
    : Array.from(text);

/** Name, staggered archetype title, subtitle, strengths and tagline. */
export function IdentityReveal({ data, layout, time }: IdentityRevealProps) {
  const compact = layout.ratio === '4:5';
  const nameRef = useRef<HTMLSpanElement>(null);
  const titleRef = useRef<HTMLSpanElement>(null);
  const subtitleRef = useRef<HTMLSpanElement>(null);
  const footerRef = useRef<HTMLSpanElement>(null);
  const name = useOverlayMotion(time, 'name');
  const subtitle = useOverlayMotion(time, 'subtitle');
  const footer = useOverlayMotion(time, 'footer');
  // The chip backing fades in with the chips, not before them.
  const chipZone = useOverlayMotion(time, 'chips');
  const fields = (data.fields ?? []).map((f) => f.trim()).filter(Boolean);
  const titleStyle = useContext(TitleStyleContext);
  const letters = useMemo(() => graphemes(data.archetype.title), [data.archetype.title]);

  const words = useMemo(() => wordIndices(letters), [letters]);

  useFitText(nameRef, [data.name], { max: 12.5, min: 9, maxWidth: CONTENT_WIDTH });
  useFitText(titleRef, [data.archetype.title], { ...layout.title, maxWidth: CONTENT_WIDTH });
  // Subtitle and footer shrink to fit the card width, so long lines never run past the frame.
  useFitText(subtitleRef, [data.archetype.subtitle, data.archetype.edition], {
    max: 11,
    min: 7,
    maxWidth: CONTENT_WIDTH,
  });
  useFitText(footerRef, [fields.join('|'), data.tagline], {
    max: 10.5,
    min: 7,
    maxWidth: CONTENT_WIDTH,
  });

  const subtitleText = [data.archetype.subtitle, data.archetype.edition]
    .filter(Boolean)
    .join(' · ');

  return (
    <div
      style={{
        paddingBottom: layout.identity.bottom,
        transform: `translateX(${layout.identity.offsetX ?? 0}px)`,
      }}
      className="absolute inset-x-0 bottom-0 flex flex-col items-center px-7"
    >
      <motion.span {...trackProps('name')} style={name} className="block w-max mx-auto rounded-full bg-[image:var(--card-zone)] px-5 py-1.5" data-paint="box">
        <span
          ref={nameRef}
          data-paint="text"
          className="inline-block font-sans leading-[18px] font-semibold tracking-[0.28em] whitespace-nowrap text-white uppercase"
        >
          {data.name}
        </span>
      </motion.span>

      <h2 className={compact ? 'mt-1' : 'mt-2'} aria-label={data.archetype.title}>
        <span
          ref={titleRef}
          key={data.archetype.title}
          aria-hidden="true"
          className="font-sans inline-block leading-[1.12] font-normal whitespace-nowrap text-[var(--card-text)] [text-shadow:0_0_18px_var(--card-glow)]"
        >
          {letters.map((letter, i) => {
            // The `word` style staggers whole words: letters share their word's slot.
            const [index, count] =
              titleStyle === 'word' ? [words.indexOf[i]!, words.count] : [i, letters.length];
            return (
              <Letter
                key={i}
                letter={letter}
                index={index}
                count={count}
                time={time}
                scramble={titleStyle === 'scramble'}
              />
            );
          })}
        </span>
      </h2>

      <motion.span {...trackProps('subtitle')} style={subtitle} className="mt-[2px] block">
        <span
          ref={subtitleRef}
          data-paint="text"
          className="inline-block font-sans text-[11px] leading-[16px] tracking-[0.32em] whitespace-nowrap text-[var(--card-subtle)] uppercase"
        >
          {subtitleText}
        </span>
      </motion.span>

      {/* Chips and footer move up by `identity.lift` without shifting the name and title. */}
      <div style={{ transform: `translateY(${-(layout.identity.lift ?? 0)}px)` }}>
      {/* 320 wide: sits inside the frame, which is inset 26 from each card edge. */}
      {/* mt-10 keeps the chips clear of the subtitle after the lift. */}
      <motion.div
        {...trackProps('chips')}
        style={chipZone}
        className={`mx-auto w-[300px] rounded-[20px] bg-[image:var(--card-zone)] p-2 ${compact ? 'mt-4' : 'mt-10'}`}
        data-paint="box"
      >
        <StrengthChips strengths={data.strengths} time={time} />
      </motion.div>

      <motion.div
        {...trackProps('footer')}
        style={footer}
        className={`flex w-full flex-col items-center ${compact ? 'mt-3' : 'mt-3'}`}
      >
        {fields.length ? (
          <>
            <span
              ref={footerRef}
              data-paint="text"
              className={`inline-block font-sans text-[10.5px] leading-[16px] font-normal tracking-[0.26em] whitespace-nowrap text-white uppercase rounded-full bg-[image:var(--card-zone)] px-4 py-1 ${compact ? 'mt-2' : 'mt-3'}`}
            >
              {fields.join(' · ')}
            </span>
          </>
        ) : (
          <>
            <div data-paint="box" className="h-px w-full bg-[var(--card-rule)]" />
            <span
              data-paint="text"
              className={`inline-block font-sans text-[12px] leading-[16px] whitespace-nowrap text-[var(--card-muted)] ${compact ? 'mt-2.5' : 'mt-3.5'}`}
            >
              {data.tagline}
            </span>
          </>
        )}
      </motion.div>
      </div>
    </div>
  );
}

/** Word index for every grapheme (spaces belong to the preceding word) and the word count. */
function wordIndices(letters: readonly string[]) {
  const indexOf: number[] = [];
  let word = 0;
  letters.forEach((letter, i) => {
    if (letter.trim() && i > 0 && !letters[i - 1]!.trim()) word++;
    indexOf.push(word);
  });
  return { indexOf, count: word + 1 };
}

function Letter({
  letter,
  index,
  count,
  time,
  scramble,
}: {
  letter: string;
  index: number;
  count: number;
  time: MotionValue<number>;
  scramble: boolean;
}) {
  const style = useOverlayMotion(time, 'title', index, count);
  const blank = letter.trim() === '';
  const glyph = useTransform(time, (t) =>
    scramble && !blank ? (scrambleGlyph(t, index, count) ?? '') : '',
  );
  const real = useTransform(glyph, (g) => (g ? 0 : 1));
  return (
    <motion.span
      {...trackProps('title', index, count)}
      style={style}
      className="relative inline-block"
    >
      {/* The real letter always holds the width, so scrambling never shifts the line. */}
      <motion.span data-paint="text" style={{ opacity: real }} className="inline-block">
        {blank ? '\u00a0' : letter}
      </motion.span>
      {scramble && !blank && (
        <motion.span aria-hidden="true" className="absolute inset-0 text-center">
          {glyph}
        </motion.span>
      )}
    </motion.span>
  );
}

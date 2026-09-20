import { Check } from 'lucide-react';
import { Section } from '../ui/Container';
import { review } from './content';
import { Reveal } from './Reveal';
import { ReviewQueueMock } from './ReviewQueueMock';
import { SectionHeading } from './SectionHeading';

export function HumanReview() {
  return (
    <Section id={review.id} aria-labelledby={`${review.id}-title`} className="scroll-mt-20">
      <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
        <Reveal className="flex flex-col gap-8">
          <SectionHeading id={review.id} title={review.title} intro={review.intro} />
          <ul className="flex flex-col gap-4">
            {review.points.map((point) => (
              <li key={point} className="flex items-start gap-3 text-app text-fg">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden="true" />
                {point}
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={0.1}>
          <ReviewQueueMock />
        </Reveal>
      </div>
    </Section>
  );
}

import type { EventHandler } from './helpers';
import { lifecycleHandlers } from './lifecycleEvents';
import { v3Handlers } from './v3Events';
import { healingHandlers } from './healingEvents';
import { hitlHandlers } from './hitlEvents';
import { intelligenceHandlers } from './intelligenceEvents';

export type { EventHandler } from './helpers';

export const eventHandlers: Record<string, EventHandler> = {
  ...lifecycleHandlers,
  ...v3Handlers,
  ...healingHandlers,
  ...hitlHandlers,
  ...intelligenceHandlers,
};

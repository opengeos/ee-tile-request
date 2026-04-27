import { Container, getContainer } from "@cloudflare/containers";

export class EeTileContainer extends Container {
  defaultPort = 7860;
  sleepAfter = "10m";
}

export default {
  async fetch(request, env) {
    return getContainer(env.EE_TILE_CONTAINER).fetch(request);
  },
};

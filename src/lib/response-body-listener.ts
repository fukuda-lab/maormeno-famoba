import { WebRequestOnBeforeRequestEventDetails } from "../types/browser-web-reqest-event-details";
import { sha256Buffer } from "./sha256";

export class ResponseBodyListener {
  private readonly responseBody: Promise<string>;
  private readonly contentHash: Promise<string>;
  private resolveResponseBody: (responseBody: string) => void;
  private resolveContentHash: (contentHash: string) => void;

  constructor(details: WebRequestOnBeforeRequestEventDetails) {
    this.responseBody = new Promise(resolve => {
      this.resolveResponseBody = resolve;
    });
    this.contentHash = new Promise(resolve => {
      this.resolveContentHash = resolve;
    });

    // Used to parse Response stream
    const filter: any = browser.webRequest.filterResponseData(
      details.requestId,
    ) as any;

    const decoder = new TextDecoder("utf-8");
    // const encoder = new TextEncoder();

    filter.ondata = event => {
      sha256Buffer(event.data).then(digest => {
        this.resolveContentHash(digest);
      });
      const str = decoder.decode(event.data, { stream: true });
      this.resolveResponseBody(str);
      filter.disconnect();
    };
  }

  public async getResponseBody() {
    return this.responseBody;
  }

  public async getContentHash() {
    return this.contentHash;
  }
}

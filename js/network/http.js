import { State } from '../state.js';
import { Utils } from '../utils/logger.js';

export const HttpClient = {
    request: function(options) {
        return new Promise(function(resolve, reject) {
            try {
                const OkHttpClient = Java.use('okhttp3.OkHttpClient');
                const Request = Java.use('okhttp3.Request$Builder');
                const MediaType = Java.use('okhttp3.MediaType');
                const RequestBody = Java.use('okhttp3.RequestBody');
                const Callback = Java.use('okhttp3.Callback');

                const client = OkHttpClient.$new();
                const builder = Request.$new().url(options.url);

                if (options.headers)
                    for (const key in options.headers)
                        builder.addHeader(key, options.headers[key]);

                if (options.method === 'POST' && options.body) {
                    const mediaType = MediaType.parse('application/json; charset=utf-8');
                    const body = RequestBody.create(mediaType, options.body);

                    builder.post(body);
                } else if (options.method === 'PUT' && options.body) {
                    const mediaType = MediaType.parse('application/json; charset=utf-8');
                    const body = RequestBody.create(mediaType, options.body);

                    builder.put(body);
                } else if (options.method === 'DELETE') {
                    builder.delete();
                }

                const CallbackClass = Java.registerClass({
                    name: 'com.frida.HttpCallback' + Date.now(),
                    implements: [Callback],
                    methods: {
                        onFailure: function(call, e) {
                            reject(new Error(e.toString()));
                        },
                        onResponse: function(call, response) {
                            try {
                                const code = response.code();
                                const body = response.body().string();

                                resolve({ code: code, body: body });
                            } catch (e) {
                                reject(e);
                            }
                        }
                    }
                });

                const request = builder.build();
                
                client.newCall(request).enqueue(CallbackClass.$new());
            } catch (e) {
                reject(e);
            }
        });
    },

    get: function(url, headers) {
        return HttpClient.request({ url: url, method: 'GET', headers: headers });
    },

    post: function(url, body, headers) {
        return HttpClient.request({ url: url, method: 'POST', body: body, headers: headers });
    },

    put: function(url, body, headers) {
        return HttpClient.request({ url: url, method: 'PUT', body: body, headers: headers });
    },

    delete: function(url, headers) {
        return HttpClient.request({ url: url, method: 'DELETE', headers: headers });
    }
};

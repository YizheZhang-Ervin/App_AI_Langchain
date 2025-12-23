package com.ai.demo.utils;

import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.memory.ChatMemory;
import dev.langchain4j.model.chat.StreamingChatModel;
import dev.langchain4j.model.chat.response.ChatResponse;
import dev.langchain4j.model.chat.response.StreamingChatResponseHandler;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;

public class MemoryUtil {

    // memory中使用
    public static AiMessage streamChat(StreamingChatModel model, ChatMemory chatMemory)
            throws ExecutionException, InterruptedException {
        CompletableFuture<AiMessage> futureAiMessage = new CompletableFuture<>();
        StreamingChatResponseHandler handler = new StreamingChatResponseHandler() {
            @Override
            public void onPartialResponse(String partialResponse) {
                System.out.print(partialResponse);
            }
            @Override
            public void onCompleteResponse(ChatResponse completeResponse) {
                futureAiMessage.complete(completeResponse.aiMessage());
            }
            @Override
            public void onError(Throwable throwable) {
            }
        };
        model.chat(chatMemory.messages(), handler);
        return futureAiMessage.get();
    }
}

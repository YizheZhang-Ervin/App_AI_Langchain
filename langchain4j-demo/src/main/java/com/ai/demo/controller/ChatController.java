package com.ai.demo.controller;

import com.ai.demo.inter.Bot;
import com.ai.demo.inter.TextUtils;
import com.ai.demo.utils.Calculator;
import com.ai.demo.utils.MemoryUtil;
import com.ai.demo.utils.RagUtil;
import dev.langchain4j.data.document.Document;
import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.data.message.SystemMessage;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.mcp.McpToolProvider;
import dev.langchain4j.mcp.client.DefaultMcpClient;
import dev.langchain4j.mcp.client.McpClient;
import dev.langchain4j.mcp.client.transport.McpTransport;
import dev.langchain4j.mcp.client.transport.http.HttpMcpTransport;
import dev.langchain4j.memory.ChatMemory;
import dev.langchain4j.memory.chat.MessageWindowChatMemory;
import dev.langchain4j.memory.chat.TokenWindowChatMemory;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.StreamingChatModel;
import dev.langchain4j.model.chat.response.ChatResponse;
import dev.langchain4j.model.chat.response.StreamingChatResponseHandler;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import dev.langchain4j.model.input.Prompt;
import dev.langchain4j.model.input.PromptTemplate;
import dev.langchain4j.model.openai.OpenAiTokenCountEstimator;
import dev.langchain4j.service.AiServices;
import dev.langchain4j.service.tool.ToolProvider;
import dev.langchain4j.store.embedding.EmbeddingMatch;
import dev.langchain4j.store.embedding.EmbeddingSearchRequest;
import dev.langchain4j.store.embedding.EmbeddingStore;
import dev.langchain4j.store.embedding.weaviate.WeaviateEmbeddingStore;
import jakarta.annotation.Resource;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;
import org.testcontainers.weaviate.WeaviateContainer;

import java.io.IOException;
import java.time.Duration;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import static dev.langchain4j.data.document.loader.FileSystemDocumentLoader.loadDocuments;
import static dev.langchain4j.data.message.UserMessage.userMessage;

@RestController
@RequestMapping("/chat")
public class ChatController {

    @Resource
    ChatModel chatModel;
    @Resource
    StreamingChatModel streamingChatModel;

    private final ExecutorService executor = Executors.newCachedThreadPool();

    @GetMapping(value = "/chat", produces = MediaType.TEXT_PLAIN_VALUE)
    public ResponseEntity<String> handleChat(@RequestParam String prompt) {
        try {
            String aiResponse = chatModel.chat(prompt);
            return ResponseEntity.ok(aiResponse);
        } catch (Exception e) {
            return ResponseEntity.ok("抱歉，处理请求时发生错误: " + e.getMessage());
        }
    }

    @GetMapping(value = "/chat/prompt")
    public String handlePromptChat(){
        String template = "Create a recipe for a {{dishType}} with the following ingredients: {{ingredients}}";
        PromptTemplate promptTemplate = PromptTemplate.from(template);
        Map<String, Object> variables = new HashMap<>();
        variables.put("dishType", "oven dish");
        variables.put("ingredients", "potato, tomato, feta, olive oil");
        Prompt prompt = promptTemplate.apply(variables);
        String response = chatModel.chat(prompt.text());
        return response;
    }

    @GetMapping(value = "/chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter handleStreamChat() {
        SseEmitter emitter = new SseEmitter(-1L);
        executor.execute(() -> {
            try {
                String userMessage = "Write a 100-word poem about Java and AI";
                CompletableFuture<ChatResponse> futureResponse = new CompletableFuture<>();
                streamingChatModel.chat(userMessage, new StreamingChatResponseHandler() {
                    @Override
                    public void onPartialResponse(String partialResponse) {
                        System.out.print(partialResponse);
                        try {
                            emitter.send(SseEmitter.event()
                                    .data(partialResponse)
                                    .id(String.valueOf(partialResponse.hashCode()))
                                    .name("chat-update"));
                        } catch (IOException e) {
                            e.printStackTrace();
                        }
                    }
                    @Override
                    public void onCompleteResponse(ChatResponse completeResponse) {
                        futureResponse.complete(completeResponse);
                        emitter.complete();
                    }
                    @Override
                    public void onError(Throwable error) {
                        futureResponse.completeExceptionally(error);
                    }
                });
                futureResponse.join();
            } catch (Exception e) {
                emitter.completeWithError(e);
            }
        });
        return emitter;
    }

    @GetMapping(value = "/chat/mcp")
    public void handleMcpChat() throws Exception{
        McpTransport transport = new HttpMcpTransport.Builder()
                .sseUrl("http://localhost:3001/sse")
                .timeout(Duration.ofSeconds(60))
                .logRequests(true)
                .logResponses(true)
                .build();

        McpClient mcpClient = new DefaultMcpClient.Builder()
                .transport(transport)
                .build();

        ToolProvider toolProvider = McpToolProvider.builder()
                .mcpClients(List.of(mcpClient))
                .build();

        Bot bot = AiServices.builder(Bot.class)
                .chatModel(chatModel)
                .toolProvider(toolProvider)
                .build();
        try {
            String response = bot.chat("What is 5+12? Use the provided tool to answer " +
                    "and always assume that the tool is correct.");
            System.out.println(response);
        } finally {
            mcpClient.close();
        }
    }

    @GetMapping(value = "/chat/memory")
    public void handleMemoryChat() throws ExecutionException, InterruptedException {
        // 创建OpenAI分词器（兼容Ollama模型）
        ChatMemory chatMemory = TokenWindowChatMemory.withMaxTokens(1000, new OpenAiTokenCountEstimator("qwen3:0.6b"));
        SystemMessage systemMessage = SystemMessage.from(
                "You are a senior developer explaining to another senior developer, "
                        + "the project you are working on is an e-commerce platform with Java back-end, " +
                        "Oracle database, and Spring Data JPA");
        chatMemory.add(systemMessage);
        UserMessage userMessage1 = userMessage(
                "How do I optimize database queries for a large-scale e-commerce platform? "
                        + "Answer short in three to five lines maximum.");
        chatMemory.add(userMessage1);
        System.out.println("[User]: " + userMessage1.singleText());
        System.out.print("[LLM]: ");

        AiMessage aiMessage1 = MemoryUtil.streamChat(streamingChatModel, chatMemory);
        chatMemory.add(aiMessage1);

        UserMessage userMessage2 = userMessage(
                "Give a concrete example implementation of the first point? " +
                        "Be short, 10 lines of code maximum.");
        chatMemory.add(userMessage2);

        System.out.println("\n\n[User]: " + userMessage2.singleText());
        System.out.print("[LLM]: ");

        AiMessage aiMessage2 = MemoryUtil.streamChat(streamingChatModel, chatMemory);
        chatMemory.add(aiMessage2);
    }

    @GetMapping(value = "/chat/tool")
    public void handleToolChat(){
        Bot assistant = AiServices.builder(Bot.class)
                .chatModel(chatModel)
                .tools(new Calculator())
                .chatMemory(MessageWindowChatMemory.withMaxMessages(10))
                .build();
        String question = "What is the square root of the sum of the numbers of letters in the words \"hello\" and \"world\"?";
        String answer = assistant.chat(question);
        System.out.println(answer);
    }

    @GetMapping(value = "/chat/msg")
    public void handleMsgChat(){
        TextUtils utils = AiServices.create(TextUtils.class, chatModel);

        String translation = utils.translate("Hello, how are you?", "italian");
        System.out.println(translation); // Ciao, come stai?

        String text = "AI, or artificial intelligence, is a branch of computer science that aims to create "
                + "machines that mimic human intelligence. This can range from simple tasks such as recognizing "
                + "patterns or speech to more complex tasks like making decisions or predictions.";

        List<String> bulletPoints = utils.summarize(text, 3);
        bulletPoints.forEach(System.out::println);
        // [
        // "- AI is a branch of computer science",
        // "- It aims to create machines that mimic human intelligence",
        // "- It can perform simple or complex tasks"
        // ]
    }

    @GetMapping(value = "/chat/rag")
    public void handleRagChat(){
        // First, let's load documents that we want to use for RAG
        List<Document> documents = loadDocuments(RagUtil.toPath("documents/"), RagUtil.glob("*.txt"));
        // Second, let's create an assistant that will have access to our documents
        Bot assistant = AiServices.builder(Bot.class)
                .chatModel(chatModel) // it should use OpenAI LLM
                .chatMemory(MessageWindowChatMemory.withMaxMessages(10)) // it should remember 10 latest messages
                .contentRetriever(RagUtil.createContentRetriever(documents)) // it should have access to our documents
                .build();
        // Lastly, let's start the conversation with the assistant. We can ask questions like:
        // - Can I cancel my reservation?
        // - I had an accident, should I pay extra?
        String agentAnswer = assistant.chat("Can I cancel my reservation?");
    }

    @GetMapping(value = "/chat/weaviate")
    public void handleWeaviate(){
        try (WeaviateContainer weaviate = new WeaviateContainer("semitechnologies/weaviate:1.22.4")) {
            weaviate.start();
            EmbeddingStore<TextSegment> embeddingStore = WeaviateEmbeddingStore.builder()
                    .scheme("http")
                    .host(weaviate.getHttpHostAddress())
                    // "Default" class is used if not specified. Must start from an uppercase letter!
                    .objectClass("Test")
                    // If true (default), then WeaviateEmbeddingStore will generate a hashed ID based on provided
                    // text segment, which avoids duplicated entries in DB. If false, then random ID will be generated.
                    .avoidDups(true)
                    // Consistency level: ONE, QUORUM (default) or ALL.
                    .consistencyLevel("ALL")
                    .build();

            EmbeddingModel embeddingModel = new AllMiniLmL6V2EmbeddingModel();

            TextSegment segment1 = TextSegment.from("I like football.");
            Embedding embedding1 = embeddingModel.embed(segment1).content();
            embeddingStore.add(embedding1, segment1);

            TextSegment segment2 = TextSegment.from("The weather is good today.");
            Embedding embedding2 = embeddingModel.embed(segment2).content();
            embeddingStore.add(embedding2, segment2);

            Embedding queryEmbedding = embeddingModel.embed("What is your favourite sport?").content();
            EmbeddingSearchRequest embeddingSearchRequest = EmbeddingSearchRequest.builder()
                    .queryEmbedding(queryEmbedding)
                    .maxResults(1)
                    .build();
            List<EmbeddingMatch<TextSegment>> matches = embeddingStore.search(embeddingSearchRequest).matches();
            EmbeddingMatch<TextSegment> embeddingMatch = matches.get(0);

            System.out.println(embeddingMatch.score()); // 0.8144288063049316
            System.out.println(embeddingMatch.embedded().text()); // I like football.
        }
    }
}

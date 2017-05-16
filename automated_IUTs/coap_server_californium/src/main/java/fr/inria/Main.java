package fr.inria;

import org.eclipse.californium.core.CoapServer;
import org.eclipse.californium.core.network.CoAPEndpoint;
import org.eclipse.californium.core.network.Endpoint;
import org.eclipse.californium.core.network.interceptors.MessageTracer;
import org.eclipse.californium.core.network.interceptors.OriginTracer;
import org.eclipse.californium.plugtests.PlugtestServer;

import java.net.InetSocketAddress;
import java.util.Arrays;

import static org.eclipse.californium.plugtests.PlugtestServer.ERR_INIT_FAILED;

public class Main {

    public static void main(String[] args) {

        System.out.println(Arrays.toString(args));

        String address =  args[0];
        Integer port = Integer.parseInt(args[1]);

        // create server
        try {
            CoapServer server = new PlugtestServer();

            server.addEndpoint(new CoAPEndpoint(new InetSocketAddress(address, port)));

            server.start();

            // add special interceptor for message traces
            for (Endpoint ep:server.getEndpoints()) {
                ep.addInterceptor(new MessageTracer());
                // Eclipse IoT metrics
                ep.addInterceptor(new OriginTracer());
            }

            System.out.println(PlugtestServer.class.getSimpleName()+" listening on port " + port);

        } catch (Exception e) {

            System.err.printf("Failed to create "+PlugtestServer.class.getSimpleName()+": %s\n", e.getMessage());
            System.err.println("Exiting");
            System.exit(ERR_INIT_FAILED);
        }

    }
}
